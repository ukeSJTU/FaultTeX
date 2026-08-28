import hashlib
import shutil
from pathlib import Path

import pytest

from faulttex.models import SuccessfulMutationResult
from faulttex.runner import run_mutation

REPOSITORY_ROOT = Path(__file__).parents[1]
MINIMAL_EXAMPLE = REPOSITORY_ROOT / "examples/minimal"


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="latexmk is not installed")
def test_minimal_example_produces_three_independent_pdfs(tmp_path: Path) -> None:
    project = MINIMAL_EXAMPLE / "project"
    original_files = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    pdf_hashes: set[str] = set()

    for mutation in sorted((MINIMAL_EXAMPLE / "mutations").glob("*.yaml")):
        output = tmp_path / mutation.stem
        result = run_mutation(project, mutation, output)

        assert isinstance(result, SuccessfulMutationResult)
        assert result.artifacts.pdf is not None
        pdf = output / result.artifacts.pdf
        assert pdf.is_file()
        pdf_hashes.add(hashlib.sha256(pdf.read_bytes()).hexdigest())

    assert len(pdf_hashes) == 3
    assert {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    } == original_files
