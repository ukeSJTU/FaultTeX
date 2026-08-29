from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from faulttex.core import apply_change, inspect_mutation
from faulttex.errors import FaultTexError
from faulttex.models import MutationSpec


def make_spec(data: dict[str, Any]) -> MutationSpec:
    return MutationSpec.model_validate(data)


def test_inspect_mutation_finds_exactly_one_target(
    latex_project: Path, mutation_data: Callable[..., dict[str, Any]]
) -> None:
    inspection = inspect_mutation(latex_project, make_spec(mutation_data()))

    assert inspection.occurrences == 1
    assert inspection.target_relative == Path("main.tex")


def test_apply_change_replaces_only_target(
    latex_project: Path, mutation_data: Callable[..., dict[str, Any]]
) -> None:
    applied = apply_change(latex_project, make_spec(mutation_data()))

    source = (latex_project / "main.tex").read_text(encoding="utf-8")
    assert "The score is 20." in source
    assert "A removable claim." in source
    assert source[applied.start_offset : applied.end_offset] == "20"
    assert (applied.start_line, applied.start_column) == (3, 14)
    assert (applied.end_line, applied.end_column) == (3, 15)


def test_apply_change_deletes_exact_text(
    latex_project: Path, mutation_data: Callable[..., dict[str, Any]]
) -> None:
    applied = apply_change(
        latex_project,
        make_spec(mutation_data(change_type="text.delete")),
    )

    source = (latex_project / "main.tex").read_text(encoding="utf-8")
    assert "A removable claim." not in source
    assert "The score is 10." in source
    assert applied.start_offset == applied.end_offset
    assert (applied.start_line, applied.start_column) == (4, 1)
    assert (applied.end_line, applied.end_column) == (4, 1)


@pytest.mark.parametrize(("old_text", "occurrences"), [("missing", 0), ("", 2)])
def test_inspect_mutation_rejects_non_unique_target(
    latex_project: Path,
    mutation_data: Callable[..., dict[str, Any]],
    old_text: str,
    occurrences: int,
) -> None:
    if old_text == "":
        (latex_project / "main.tex").write_text("The score is 10.\nThe score is 10.\n")
        old_text = "10"
    spec = make_spec(mutation_data(old_text=old_text))

    with pytest.raises(FaultTexError, match=rf"occurred {occurrences} times") as caught:
        inspect_mutation(latex_project, spec)

    assert caught.value.stage == "match"


@pytest.mark.parametrize("unsafe", ["/tmp/main.tex", "../main.tex"])
def test_inspect_mutation_rejects_unsafe_target_paths(
    latex_project: Path,
    mutation_data: Callable[..., dict[str, Any]],
    unsafe: str,
) -> None:
    spec = make_spec(mutation_data(file=unsafe))

    with pytest.raises(FaultTexError) as caught:
        inspect_mutation(latex_project, spec)

    assert caught.value.stage == "file"


def test_inspect_mutation_rejects_symlink_escape(
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    outside = tmp_path / "outside.tex"
    outside.write_text("The score is 10.", encoding="utf-8")
    (latex_project / "link.tex").symlink_to(outside)
    spec = make_spec(mutation_data(file="link.tex"))

    with pytest.raises(FaultTexError, match="escapes") as caught:
        inspect_mutation(latex_project, spec)

    assert caught.value.stage == "file"


def test_inspect_mutation_requires_tex_entrypoint(
    latex_project: Path, mutation_data: Callable[..., dict[str, Any]]
) -> None:
    (latex_project / "main.txt").write_text("not tex", encoding="utf-8")
    spec = make_spec(mutation_data(entrypoint="main.txt"))

    with pytest.raises(FaultTexError, match="must be a .tex file"):
        inspect_mutation(latex_project, spec)
