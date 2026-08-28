import json
import shutil
import tempfile
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from .compiler import Compiler, LatexmkCompiler
from .core import apply_change, inspect_mutation, load_mutation, resolve_project_root
from .errors import FaultTexError
from .models import (
    ArtifactPaths,
    FailedMutationResult,
    MutationResult,
    SuccessfulMutationResult,
)

RESULT_NAME = "result.json"
LOG_NAME = "compile.log"
SOURCE_NAME = "source"


def _safe_artifact_path(output: Path, value: str) -> Path | None:
    candidate = (output / value).resolve()
    if candidate == output or not candidate.is_relative_to(output):
        return None
    return candidate


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _previous_artifacts(output: Path) -> set[Path]:
    result_path = output / RESULT_NAME
    paths = {result_path, output / LOG_NAME, output / SOURCE_NAME}
    if not result_path.is_file():
        return paths
    try:
        raw = cast(dict[str, object], json.loads(result_path.read_text(encoding="utf-8")))
        artifacts = raw.get("artifacts", {})
        if isinstance(artifacts, dict):
            artifact_values = cast(dict[str, object], artifacts)
            for value in artifact_values.values():
                if isinstance(value, str):
                    candidate = _safe_artifact_path(output, value)
                    if candidate is not None:
                        paths.add(candidate)
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    return paths


def prepare_output(output: Path, overwrite: bool) -> Path:
    resolved = output.resolve()
    try:
        if resolved.exists() and not resolved.is_dir():
            raise FaultTexError("output", f"Output path is not a directory: {output}")
        if resolved.exists() and any(resolved.iterdir()) and not overwrite:
            raise FaultTexError(
                "output", f"Output directory is not empty; use --overwrite: {output}"
            )
        resolved.mkdir(parents=True, exist_ok=True)
        if overwrite:
            for artifact in _previous_artifacts(resolved):
                _remove_path(artifact)
    except FaultTexError:
        raise
    except OSError as exc:
        raise FaultTexError(
            "output", f"Could not prepare output directory {output}: {exc}"
        ) from exc
    return resolved


def write_json_model(path: Path, model: BaseModel) -> None:
    payload = model.model_dump(mode="json", by_alias=True, exclude_none=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise FaultTexError("output", f"Could not write {path}: {exc}") from exc


def _retain_source(workspace: Path, output: Path) -> None:
    destination = output / SOURCE_NAME
    try:
        _remove_path(destination)
        shutil.copytree(workspace, destination)
    except OSError as exc:
        raise FaultTexError("output", f"Could not retain mutated source: {exc}") from exc


def run_mutation(
    project: Path,
    mutation_path: Path,
    output: Path,
    *,
    keep_source: bool = False,
    overwrite: bool = False,
    compiler: Compiler | None = None,
) -> MutationResult:
    output_root = prepare_output(output, overwrite)
    artifacts = ArtifactPaths()
    workspace: Path | None = None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    failure: FaultTexError | None = None

    try:
        spec = load_mutation(mutation_path)
        project_root = resolve_project_root(project)
        inspect_mutation(project_root, spec)
        temporary = tempfile.TemporaryDirectory(prefix="faulttex-")
        workspace = Path(temporary.name) / "project"
        try:
            shutil.copytree(project_root, workspace)
        except OSError as exc:
            raise FaultTexError("apply", f"Could not copy LaTeX project: {exc}") from exc

        inspection = apply_change(workspace, spec)
        log_path = output_root / LOG_NAME
        selected_compiler = compiler or LatexmkCompiler()
        try:
            compiled_pdf = selected_compiler.compile(
                workspace,
                Path(spec.entrypoint),
                log_path,
            )
        finally:
            if log_path.is_file():
                artifacts.log = LOG_NAME

        pdf_name = inspection.entrypoint.stem + ".pdf"
        pdf_output = output_root / pdf_name
        try:
            _remove_path(pdf_output)
            shutil.copy2(compiled_pdf, pdf_output)
        except OSError as exc:
            raise FaultTexError("output", f"Could not preserve compiled PDF: {exc}") from exc
        artifacts.pdf = pdf_name
    except FaultTexError as exc:
        failure = exc
    finally:
        if keep_source and workspace is not None and workspace.is_dir():
            try:
                _retain_source(workspace, output_root)
                artifacts.source = SOURCE_NAME
            except FaultTexError as output_exc:
                failure = output_exc
        if temporary is not None:
            temporary.cleanup()

    result: MutationResult
    if failure is None:
        result = SuccessfulMutationResult(artifacts=artifacts)
    else:
        result = FailedMutationResult(
            stage=failure.stage,
            error=str(failure),
            artifacts=artifacts,
        )

    write_json_model(output_root / RESULT_NAME, result)
    return result
