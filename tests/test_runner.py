import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from faulttex.errors import FaultTexError
from faulttex.models import FailedMutationResult, SuccessfulMutationResult
from faulttex.runner import run_mutation


class SuccessfulCompiler:
    def compile(self, project: Path, entrypoint: Path, log_path: Path) -> Path:
        log_path.write_text("compiled\n", encoding="utf-8")
        pdf = project / entrypoint.with_suffix(".pdf")
        pdf.write_bytes(b"%PDF-1.4\n% fake\n")
        return pdf


class FailingCompiler:
    def compile(self, project: Path, entrypoint: Path, log_path: Path) -> Path:
        del project, entrypoint
        log_path.write_text("compiler failed\n", encoding="utf-8")
        raise FaultTexError("compile", "LaTeX compilation returned exit code 1.")


def write_mutation(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_run_mutation_writes_success_artifacts_and_preserves_original(
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    mutation = tmp_path / "mutation.yaml"
    output = tmp_path / "output"
    write_mutation(mutation, mutation_data())
    original = (latex_project / "main.tex").read_text(encoding="utf-8")

    result = run_mutation(
        latex_project,
        mutation,
        output,
        keep_source=True,
        compiler=SuccessfulCompiler(),
    )

    assert isinstance(result, SuccessfulMutationResult)
    assert (output / "main.pdf").is_file()
    assert (output / "compile.log").read_text() == "compiled\n"
    assert "The score is 20." in (output / "source/main.tex").read_text()
    assert (latex_project / "main.tex").read_text(encoding="utf-8") == original
    stored = json.loads((output / "result.json").read_text())
    assert stored == {
        "schema": 1,
        "status": "success",
        "artifacts": {"pdf": "main.pdf", "log": "compile.log", "source": "source"},
    }


def test_run_mutation_records_schema_failure(tmp_path: Path, latex_project: Path) -> None:
    mutation = tmp_path / "bad.yaml"
    mutation.write_text("schema: 2\n", encoding="utf-8")
    output = tmp_path / "output"

    result = run_mutation(latex_project, mutation, output, compiler=SuccessfulCompiler())

    assert isinstance(result, FailedMutationResult)
    assert result.stage == "schema"
    assert json.loads((output / "result.json").read_text())["stage"] == "schema"
    assert not (output / "compile.log").exists()


def test_run_mutation_records_compile_failure_and_retains_source(
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    mutation = tmp_path / "mutation.yaml"
    output = tmp_path / "output"
    write_mutation(mutation, mutation_data())

    result = run_mutation(
        latex_project,
        mutation,
        output,
        keep_source=True,
        compiler=FailingCompiler(),
    )

    assert isinstance(result, FailedMutationResult)
    assert result.stage == "compile"
    assert result.artifacts.log == "compile.log"
    assert result.artifacts.source == "source"
    assert "The score is 20." in (output / "source/main.tex").read_text()
    assert not (output / "main.pdf").exists()


def test_run_mutation_rejects_project_symlink_escape_before_copy(
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    outside = tmp_path / "outside.tex"
    outside.write_text("The score is 10.", encoding="utf-8")
    (latex_project / "link.tex").symlink_to(outside)
    mutation = tmp_path / "mutation.yaml"
    output = tmp_path / "output"
    write_mutation(mutation, mutation_data(file="link.tex"))

    result = run_mutation(latex_project, mutation, output, compiler=SuccessfulCompiler())

    assert isinstance(result, FailedMutationResult)
    assert result.stage == "file"
    assert "escapes" in result.error
    assert outside.read_text(encoding="utf-8") == "The score is 10."


def test_run_mutation_refuses_nonempty_output_without_overwrite(
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    mutation = tmp_path / "mutation.yaml"
    output = tmp_path / "output"
    output.mkdir()
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")
    write_mutation(mutation, mutation_data())

    with pytest.raises(FaultTexError, match="not empty") as caught:
        run_mutation(latex_project, mutation, output, compiler=SuccessfulCompiler())

    assert caught.value.stage == "output"


def test_run_mutation_overwrite_preserves_unrelated_files(
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    mutation = tmp_path / "mutation.yaml"
    output = tmp_path / "output"
    write_mutation(mutation, mutation_data())
    run_mutation(latex_project, mutation, output, compiler=SuccessfulCompiler())
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")

    result = run_mutation(
        latex_project,
        mutation,
        output,
        overwrite=True,
        compiler=SuccessfulCompiler(),
    )

    assert isinstance(result, SuccessfulMutationResult)
    assert (output / "unrelated.txt").read_text() == "keep"
