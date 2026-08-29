from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .errors import FaultTexError
from .models import MutationIdentity, MutationSpec, TextDeleteChange, TextReplaceChange


@dataclass(frozen=True, slots=True)
class MutationInspection:
    project: Path
    entrypoint: Path
    target: Path
    target_relative: Path
    occurrences: int


@dataclass(frozen=True, slots=True)
class AppliedChange:
    inspection: MutationInspection
    start_offset: int
    end_offset: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise FaultTexError("schema", f"Could not read mutation spec {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise FaultTexError("schema", f"Invalid mutation YAML in {path}: {exc}") from exc


def load_mutation_id(path: Path) -> str:
    raw = _load_yaml(path)
    try:
        return MutationIdentity.model_validate(raw).id
    except ValidationError as exc:
        raise FaultTexError("schema", f"Invalid mutation identity in {path}: {exc}") from exc


def load_mutation(path: Path) -> MutationSpec:
    raw = _load_yaml(path)
    try:
        return MutationSpec.model_validate(raw)
    except ValidationError as exc:
        raise FaultTexError("schema", f"Invalid mutation schema in {path}: {exc}") from exc


def resolve_project_root(project: Path) -> Path:
    try:
        resolved = project.resolve(strict=True)
    except OSError as exc:
        raise FaultTexError("file", f"LaTeX project does not exist: {project}") from exc
    if not resolved.is_dir():
        raise FaultTexError("file", f"LaTeX project is not a directory: {project}")
    return resolved


def resolve_project_file(project: Path, value: str, field: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise FaultTexError("file", f"{field} must be relative to the project: {value}")

    try:
        resolved = (project / relative).resolve(strict=True)
    except OSError as exc:
        raise FaultTexError("file", f"{field} does not exist in the project: {value}") from exc

    if not resolved.is_relative_to(project):
        raise FaultTexError("file", f"{field} escapes the project root: {value}")
    if not resolved.is_file():
        raise FaultTexError("file", f"{field} is not a file: {value}")
    return resolved


def _needle_and_replacement(spec: MutationSpec) -> tuple[str, str]:
    change = spec.change
    if isinstance(change, TextReplaceChange):
        needle = change.before_context + change.old_text + change.after_context
        replacement = change.before_context + change.new_text + change.after_context
    else:
        assert isinstance(change, TextDeleteChange)
        needle = change.before_context + change.text + change.after_context
        replacement = change.before_context + change.after_context
    return needle, replacement


def inspect_mutation(project: Path, spec: MutationSpec) -> MutationInspection:
    root = resolve_project_root(project)
    entrypoint = resolve_project_file(root, spec.entrypoint, "entrypoint")
    if entrypoint.suffix.lower() != ".tex":
        raise FaultTexError("file", f"entrypoint must be a .tex file: {spec.entrypoint}")

    target = resolve_project_file(root, spec.change.file, "change.file")
    try:
        source = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FaultTexError(
            "apply", f"Could not read target file {spec.change.file}: {exc}"
        ) from exc

    needle, _ = _needle_and_replacement(spec)
    occurrences = source.count(needle)
    if occurrences != 1:
        raise FaultTexError(
            "match",
            f"The complete target text occurred {occurrences} times in {spec.change.file}.",
        )

    return MutationInspection(
        project=root,
        entrypoint=entrypoint,
        target=target,
        target_relative=Path(spec.change.file),
        occurrences=occurrences,
    )


def _line_and_column(source: str, offset: int) -> tuple[int, int]:
    return source.count("\n", 0, offset) + 1, offset - source.rfind("\n", 0, offset)


def apply_change(project: Path, spec: MutationSpec) -> AppliedChange:
    inspection = inspect_mutation(project, spec)
    try:
        source = inspection.target.read_text(encoding="utf-8")
        needle, replacement = _needle_and_replacement(spec)
        match_start = source.index(needle)
        target_start = match_start + len(spec.change.before_context)
        if isinstance(spec.change, TextReplaceChange):
            target_end = target_start + len(spec.change.new_text)
        else:
            target_end = target_start
        mutated = source[:match_start] + replacement + source[match_start + len(needle) :]
        inspection.target.write_text(mutated, encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FaultTexError(
            "apply", f"Could not update target file {spec.change.file}: {exc}"
        ) from exc

    start_line, start_column = _line_and_column(mutated, target_start)
    final_character = target_start if target_end == target_start else target_end - 1
    end_line, end_column = _line_and_column(mutated, final_character)
    return AppliedChange(
        inspection=inspection,
        start_offset=target_start,
        end_offset=target_end,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_column,
    )
