import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from typer.testing import CliRunner

from faulttex.cli import app
from faulttex.compiler import LatexmkCompiler

runner = CliRunner()


def fake_compile(
    self: LatexmkCompiler,
    project: Path,
    entrypoint: Path,
    log_path: Path,
) -> Path:
    del self
    log_path.write_text("compiled\n", encoding="utf-8")
    pdf = project / entrypoint.with_suffix(".pdf")
    pdf.write_bytes(b"%PDF-1.4\n% fake\n")
    return pdf


def write_mutation(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_check_json_success(
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    mutation = tmp_path / "mutation.yaml"
    write_mutation(mutation, mutation_data())

    result = runner.invoke(app, ["check", str(latex_project), str(mutation), "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "status": "success",
        "file": "main.tex",
        "occurrences": 1,
    }


def test_check_json_failure(latex_project: Path, tmp_path: Path) -> None:
    mutation = tmp_path / "mutation.yaml"
    mutation.write_text("schema: 2\n", encoding="utf-8")

    result = runner.invoke(app, ["check", str(latex_project), str(mutation), "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["stage"] == "schema"


def test_apply_success(
    monkeypatch: Any,
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    monkeypatch.setattr(LatexmkCompiler, "compile", fake_compile)
    mutation = tmp_path / "mutation.yaml"
    output = tmp_path / "output"
    write_mutation(mutation, mutation_data())

    result = runner.invoke(
        app,
        ["apply", str(latex_project), str(mutation), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert (output / "main.pdf").is_file()
    assert json.loads((output / "result.json").read_text())["status"] == "success"


def test_batch_uses_sorted_six_digit_ids_and_continues_failures(
    monkeypatch: Any,
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    monkeypatch.setattr(LatexmkCompiler, "compile", fake_compile)
    mutations = tmp_path / "mutations"
    mutations.mkdir()
    write_mutation(mutations / "b.yaml", mutation_data(new_text="30"))
    write_mutation(mutations / "a.yaml", mutation_data(new_text="20"))
    (mutations / "c.yaml").write_text("schema: 2\n", encoding="utf-8")
    output = tmp_path / "batch"

    result = runner.invoke(
        app,
        [
            "--quiet",
            "batch",
            str(latex_project),
            str(mutations),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    aggregate = json.loads((output / "batch-result.json").read_text())
    assert aggregate["total"] == 3
    assert aggregate["succeeded"] == 2
    assert aggregate["failed"] == 1
    assert [run["id"] for run in aggregate["runs"]] == ["000001", "000002", "000003"]
    assert [run["mutation"] for run in aggregate["runs"]] == ["a.yaml", "b.yaml", "c.yaml"]
    assert (output / "000001/main.pdf").is_file()
    assert (output / "000002/main.pdf").is_file()
    assert not (output / "000003/main.pdf").exists()


def test_batch_recursive_discovers_nested_specs(
    monkeypatch: Any,
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    monkeypatch.setattr(LatexmkCompiler, "compile", fake_compile)
    mutations = tmp_path / "mutations"
    nested = mutations / "nested"
    nested.mkdir(parents=True)
    write_mutation(nested / "change.yml", mutation_data())

    without_recursive = runner.invoke(
        app,
        [
            "batch",
            str(latex_project),
            str(mutations),
            "--output",
            str(tmp_path / "without"),
        ],
    )
    with_recursive = runner.invoke(
        app,
        [
            "--quiet",
            "batch",
            str(latex_project),
            str(mutations),
            "--output",
            str(tmp_path / "with"),
            "--recursive",
        ],
    )

    assert without_recursive.exit_code == 1
    assert with_recursive.exit_code == 0
    aggregate = json.loads((tmp_path / "with/batch-result.json").read_text())
    assert aggregate["runs"][0]["mutation"] == "nested/change.yml"


def test_cli_usage_error_is_exit_code_two() -> None:
    result = runner.invoke(app, ["apply"])

    assert result.exit_code == 2
