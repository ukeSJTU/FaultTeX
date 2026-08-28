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
        "id": "test_mutation",
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
    assert (output / "mutation.yaml").read_bytes() == mutation.read_bytes()
    stored = json.loads((output / "result.json").read_text())
    assert stored["id"] == "test_mutation"
    assert stored["status"] == "success"


def test_batch_uses_mutation_ids_and_continues_non_identity_failures(
    monkeypatch: Any,
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    monkeypatch.setattr(LatexmkCompiler, "compile", fake_compile)
    mutations = tmp_path / "mutations"
    mutations.mkdir()
    write_mutation(
        mutations / "b.yaml",
        mutation_data(mutation_id="second_mutation", new_text="30"),
    )
    write_mutation(
        mutations / "a.yaml",
        mutation_data(mutation_id="first_mutation", new_text="20"),
    )
    invalid = mutation_data(mutation_id="invalid_schema")
    invalid["schema"] = 2
    write_mutation(mutations / "c.yaml", invalid)
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
    assert [item["id"] for item in aggregate["mutations"]] == [
        "first_mutation",
        "second_mutation",
        "invalid_schema",
    ]
    assert [item["input"] for item in aggregate["mutations"]] == [
        "a.yaml",
        "b.yaml",
        "c.yaml",
    ]
    assert (output / "mutations/first_mutation/main.pdf").is_file()
    assert (output / "mutations/second_mutation/main.pdf").is_file()
    assert not (output / "mutations/invalid_schema/main.pdf").exists()
    failed_result = json.loads((output / "mutations/invalid_schema/result.json").read_text())
    assert failed_result["id"] == "invalid_schema"
    assert failed_result["stage"] == "schema"


def test_batch_identity_preflight_writes_aggregate_and_executes_nothing(
    monkeypatch: Any,
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    def unexpected_compile(*args: object, **kwargs: object) -> Path:
        del args, kwargs
        raise AssertionError("identity preflight must finish before compilation")

    monkeypatch.setattr(LatexmkCompiler, "compile", unexpected_compile)
    mutations = tmp_path / "mutations"
    mutations.mkdir()
    write_mutation(mutations / "a.yaml", mutation_data(mutation_id="duplicate"))
    write_mutation(
        mutations / "b.yaml",
        mutation_data(mutation_id="duplicate", new_text="30"),
    )
    missing_id = mutation_data()
    del missing_id["id"]
    write_mutation(mutations / "c.yaml", missing_id)
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
    assert aggregate["status"] == "failed"
    assert aggregate["stage"] == "schema"
    assert "duplicate id 'duplicate'" in aggregate["error"]
    assert "c.yaml" in aggregate["error"]
    assert not (output / "mutations").exists()


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
    assert aggregate["mutations"][0]["input"] == "nested/change.yml"


def test_batch_overwrite_replaces_owned_mutations_and_preserves_unrelated_files(
    monkeypatch: Any,
    latex_project: Path,
    tmp_path: Path,
    mutation_data: Callable[..., dict[str, Any]],
) -> None:
    monkeypatch.setattr(LatexmkCompiler, "compile", fake_compile)
    mutations = tmp_path / "mutations"
    mutations.mkdir()
    write_mutation(mutations / "change.yaml", mutation_data(mutation_id="old_mutation"))
    output = tmp_path / "batch"

    first = runner.invoke(
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
    assert first.exit_code == 0
    (output / "unrelated.txt").write_text("keep", encoding="utf-8")
    write_mutation(
        mutations / "change.yaml",
        mutation_data(mutation_id="new_mutation", new_text="30"),
    )

    second = runner.invoke(
        app,
        [
            "--quiet",
            "batch",
            str(latex_project),
            str(mutations),
            "--output",
            str(output),
            "--overwrite",
        ],
    )

    assert second.exit_code == 0
    assert not (output / "mutations/old_mutation").exists()
    assert (output / "mutations/new_mutation/main.pdf").is_file()
    assert (output / "unrelated.txt").read_text() == "keep"


def test_cli_usage_error_is_exit_code_two() -> None:
    result = runner.invoke(app, ["apply"])

    assert result.exit_code == 2
