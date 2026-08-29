import hashlib
import shutil
from pathlib import Path
from typing import cast

import pytest
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject

from faulttex.models import SuccessfulMutationResult
from faulttex.runner import run_mutation

REPOSITORY_ROOT = Path(__file__).parents[1]
MINIMAL_EXAMPLE = REPOSITORY_ROOT / "examples/minimal"


def _faulttex_annotations(pdf: Path) -> list[tuple[int, DictionaryObject]]:
    reader = PdfReader(pdf)
    annotations: list[tuple[int, DictionaryObject]] = []
    for page_number, page in enumerate(reader.pages, 1):
        for reference in page.get("/Annots", []):
            annotation = cast(DictionaryObject, reference.get_object())
            if str(annotation.get("/NM", "")).startswith("faulttex-"):
                annotations.append((page_number, annotation))
    return annotations


@pytest.mark.skipif(
    shutil.which("latexmk") is None or shutil.which("synctex") is None,
    reason="latexmk and synctex are required",
)
def test_minimal_example_produces_three_independent_annotated_pdfs(tmp_path: Path) -> None:
    project = MINIMAL_EXAMPLE / "project"
    original_files = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    expected_subtypes = {
        "delete-claim": ["/Text"],
        "replace-number": ["/Highlight", "/Text"],
        "reverse-conclusion": ["/Highlight", "/Text"],
    }
    pdf_hashes: set[str] = set()

    for mutation in sorted((MINIMAL_EXAMPLE / "mutations").glob("*.yaml")):
        output = tmp_path / mutation.stem
        result = run_mutation(project, mutation, output)

        assert isinstance(result, SuccessfulMutationResult)
        assert result.artifacts.pdf == "main.pdf"
        pdf = output / "main.pdf"
        assert pdf.is_file()
        pdf_hashes.add(hashlib.sha256(pdf.read_bytes()).hexdigest())
        annotations = _faulttex_annotations(pdf)
        assert [str(annotation["/Subtype"]) for _, annotation in annotations] == (
            expected_subtypes[mutation.stem]
        )
        assert all(result.id in str(annotation["/Contents"]) for _, annotation in annotations)

    assert len(pdf_hashes) == 3
    assert {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    } == original_files


@pytest.mark.skipif(
    shutil.which("latexmk") is None or shutil.which("synctex") is None,
    reason="latexmk and synctex are required",
)
def test_long_replacement_highlight_spans_rendered_lines(tmp_path: Path) -> None:
    mutation = tmp_path / "long-replacement.yaml"
    mutation.write_text(
        """schema: 1
id: replace_abstract_claim_and_metrics
entrypoint: main.tex
description: Replace a complete abstract passage with a longer contradictory claim.
label: compound_claim_evidence_mismatch
change:
  type: text.replace
  file: main.tex
  before_context: |-
    before predicting whether
  old_text: |2-
     a claim is supported. On EvidenceBench, CEA reaches an
    accuracy of $84.6\\%$ while retaining competitive calibration error.
  new_text: |2-
     a claim is unsupported. On EvidenceBench, CEA reaches an
    accuracy of $74.6\\%$ while exhibiting substantially worse calibration error.
  after_context: |2-
     Controlled
""",
        encoding="utf-8",
    )

    output = tmp_path / "output"
    result = run_mutation(MINIMAL_EXAMPLE / "project", mutation, output)

    assert isinstance(result, SuccessfulMutationResult)
    annotations = _faulttex_annotations(output / "main.pdf")
    highlights = [
        annotation for _, annotation in annotations if str(annotation["/Subtype"]) == "/Highlight"
    ]
    assert len(highlights) == 1
    quad_points = cast(ArrayObject, highlights[0]["/QuadPoints"])
    assert len(quad_points) >= 16


@pytest.mark.skipif(
    shutil.which("latexmk") is None or shutil.which("synctex") is None,
    reason="latexmk and synctex are required",
)
def test_math_times_replacement_produces_native_highlight(tmp_path: Path) -> None:
    mutation = tmp_path / "math-times.yaml"
    mutation.write_text(
        r"""schema: 1
id: replace_accuracy_with_multiplier
entrypoint: main.tex
description: Replace an accuracy value with a rendered multiplication claim.
label: number_corruption
change:
  type: text.replace
  file: main.tex
  before_context: ''
  old_text: 'accuracy of $84.6\%$'
  new_text: 'accuracy is $2.5\times$ higher'
  after_context: ' while retaining competitive calibration error.'
""",
        encoding="utf-8",
    )

    output = tmp_path / "output"
    result = run_mutation(MINIMAL_EXAMPLE / "project", mutation, output)

    assert isinstance(result, SuccessfulMutationResult)
    annotations = _faulttex_annotations(output / "main.pdf")
    assert [str(annotation["/Subtype"]) for _, annotation in annotations] == [
        "/Highlight",
        "/Text",
    ]
