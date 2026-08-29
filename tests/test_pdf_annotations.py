import pytest

from faulttex.pdf_annotations import (
    PdfAnnotationError,
    latex_to_visible_text,
    parse_synctex_regions,
)


@pytest.mark.parametrize(
    ("latex", "visible"),
    [
        ("74.6", "74.6"),
        (r"$74.6\%$", "74.6%"),
        (r"\emph{reduces}", "reduces"),
        (r"A~B \& C", "A B & C"),
        (
            "a claim is unsupported.\nAccuracy is $74.6\\%$.",
            "a claim is unsupported. Accuracy is 74.6%.",
        ),
    ],
)
def test_latex_to_visible_text_handles_supported_subset(latex: str, visible: str) -> None:
    assert latex_to_visible_text(latex) == visible


def test_latex_to_visible_text_rejects_unmapped_commands() -> None:
    with pytest.raises(PdfAnnotationError, match="without a deterministic"):
        latex_to_visible_text(r"\frac{1}{2}")


def test_parse_synctex_regions_converts_output_to_candidate_boxes() -> None:
    output = """SyncTeX result begin
Output:main.pdf
Page:1
h:99.272774
v:280.156555
x:99.272774
y:270.747867
W:413.454407
H:9.408688
before:
offset:-1
SyncTeX result end
"""

    regions = parse_synctex_regions(output)

    assert len(regions) == 1
    assert regions[0].page == 1
    assert regions[0].left == pytest.approx(96.272774)
    assert regions[0].top == pytest.approx(266.747867)
    assert regions[0].right == pytest.approx(515.727181)
    assert regions[0].bottom == pytest.approx(284.156555)
    assert regions[0].point_x == pytest.approx(99.272774)
    assert regions[0].point_top == pytest.approx(270.747867)
