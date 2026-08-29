import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pdfplumber
from pdfplumber.pdf import PDF
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight, Text
from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject

from .core import AppliedChange
from .models import MutationSpec, TextDeleteChange, TextReplaceChange


class PdfAnnotationError(Exception):
    """A deterministic failure to resolve, write, or verify a mutation annotation."""


@dataclass(frozen=True, slots=True)
class SyncTexRegion:
    page: int
    left: float
    top: float
    right: float
    bottom: float
    point_x: float
    point_top: float


@dataclass(frozen=True, slots=True)
class RenderedMatch:
    start_index: int
    end_index: int
    page_chars: tuple[tuple[int, Mapping[str, Any]], ...]


@dataclass(frozen=True, slots=True)
class PdfAnnotationPlacement:
    page: int
    rectangles: tuple[tuple[float, float, float, float], ...]
    note_top: float


@dataclass(frozen=True, slots=True)
class PdfAnnotationResult:
    kind: str
    search_text: str | None
    placements: tuple[PdfAnnotationPlacement, ...]


_SIMPLE_COMMAND = re.compile(
    r"\\(?:emph|textbf|textit|textnormal|textrm|textsf|texttt|mathrm|mathbf)\{([^{}]*)\}"
)
_SYNCTEX_FIELD = re.compile(r"^(Page|x|y|h|v|W|H):(.+)$", re.MULTILINE)
_ANCHOR_LIMIT = 240


def latex_to_visible_text(value: str) -> str:
    """Convert a deliberately small, unambiguous LaTeX subset to rendered text."""
    # TODO(schema > 1): Allow mutation specs to provide an explicit rendered_text target
    # for replacements whose raw LaTeX cannot be mapped deterministically to PDF text.
    visible = value
    previous = None
    while visible != previous:
        previous = visible
        visible = _SIMPLE_COMMAND.sub(r"\1", visible)

    replacements = {
        r"\times": "×",
        r"\%": "%",
        r"\&": "&",
        r"\_": "_",
        r"\#": "#",
        r"\$": "$",
        r"\{": "{",
        r"\}": "}",
        "~": " ",
    }
    for source, replacement in replacements.items():
        visible = visible.replace(source, replacement)
    visible = re.sub(r"\s+", " ", visible.replace("$", "")).strip()

    if not visible:
        raise PdfAnnotationError("The LaTeX source has no visible text to locate.")
    if "\\" in visible:
        raise PdfAnnotationError(
            "The LaTeX source contains commands without a deterministic PDF-text mapping."
        )
    return visible


def parse_synctex_regions(output: str) -> tuple[SyncTexRegion, ...]:
    regions: list[SyncTexRegion] = []
    for block in output.split("Output:")[1:]:
        values = {match.group(1): match.group(2) for match in _SYNCTEX_FIELD.finditer(block)}
        if not {"Page", "x", "y", "h", "v", "W", "H"}.issubset(values):
            continue
        page = int(values["Page"])
        horizontal = float(values["h"])
        baseline = float(values["v"])
        width = float(values["W"])
        height = float(values["H"])
        regions.append(
            SyncTexRegion(
                page=page,
                left=horizontal - 3,
                top=baseline - height - 4,
                right=horizontal + width + 3,
                bottom=baseline + 4,
                point_x=float(values["x"]),
                point_top=float(values["y"]),
            )
        )
    return tuple(regions)


def _synctex_regions(applied: AppliedChange, pdf: Path) -> tuple[SyncTexRegion, ...]:
    inspection = applied.inspection
    regions: list[SyncTexRegion] = []
    for line in range(applied.start_line, applied.end_line + 1):
        column = applied.start_column if line == applied.start_line else 1
        command = [
            "synctex",
            "view",
            "-i",
            f"{line}:{column}:{inspection.target_relative.as_posix()}",
            "-o",
            pdf.relative_to(inspection.project).as_posix(),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=inspection.project,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise PdfAnnotationError(f"Could not run SyncTeX: {exc}") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise PdfAnnotationError(
                f"SyncTeX failed for {inspection.target_relative}:{line}: {detail}"
            )
        regions.extend(parse_synctex_regions(completed.stdout))

    unique = tuple(dict.fromkeys(regions))
    if not unique:
        raise PdfAnnotationError("SyncTeX returned no candidate PDF regions.")
    return unique


def _intersects(char: Mapping[str, Any], region: SyncTexRegion) -> bool:
    return bool(
        float(char["x1"]) >= region.left
        and float(char["x0"]) <= region.right
        and float(char["bottom"]) >= region.top
        and float(char["top"]) <= region.bottom
    )


def _candidate_text(
    document: PDF,
    pages: Sequence[int],
) -> tuple[str, tuple[tuple[int, Mapping[str, Any] | None], ...]]:
    text_parts: list[str] = []
    positions: list[tuple[int, Mapping[str, Any] | None]] = []
    for page_number in pages:
        if page_number < 1 or page_number > len(document.pages):
            continue
        page = document.pages[page_number - 1]
        textmap = page.get_textmap()
        tuples = cast(list[tuple[str, Mapping[str, Any] | None]], textmap.tuples)
        for text, char in tuples:
            text_parts.append(text)
            positions.extend((page_number, char) for _ in text)
        text_parts.append("\n")
        positions.append((page_number, None))
    return "".join(text_parts), tuple(positions)


def _find_rendered_matches(
    document: PDF,
    pages: Sequence[int],
    search_text: str,
) -> tuple[RenderedMatch, ...]:
    candidate_text, positions = _candidate_text(document, pages)
    # PDF extractors may add virtual layout whitespace that has no counterpart in the
    # source. Remove it from the matching stream while keeping every remaining character
    # paired with its original page and geometry.
    normalized_text: list[str] = []
    normalized_positions: list[tuple[int, Mapping[str, Any] | None]] = []
    for character, position in zip(candidate_text, positions, strict=True):
        if character.isspace():
            continue
        normalized_text.append(character)
        normalized_positions.append(position)
    candidate_text = "".join(normalized_text)
    positions = tuple(normalized_positions)
    search_text = "".join(character for character in search_text if not character.isspace())

    pattern_parts: list[str] = []
    for index, character in enumerate(search_text):
        pattern_parts.append(re.escape(character))
        if (
            character.isalnum()
            and index + 1 < len(search_text)
            and search_text[index + 1].isalnum()
        ):
            # PDF text extraction preserves TeX's discretionary line-break hyphen, so
            # a rendered word such as "reduces" may appear as "re-\nduces".
            pattern_parts.append("-?")
    pattern = "".join(pattern_parts)
    matches: list[RenderedMatch] = []
    for match in re.finditer(pattern, candidate_text):
        page_chars = tuple(
            (page, char)
            for page, char in positions[match.start() : match.end()]
            if char is not None
        )
        if page_chars:
            matches.append(
                RenderedMatch(
                    start_index=match.start(),
                    end_index=match.end(),
                    page_chars=page_chars,
                )
            )
    return tuple(matches)


def _line_rectangles(
    chars: Sequence[Mapping[str, Any]],
    page_height: float,
) -> tuple[tuple[float, float, float, float], ...]:
    lines: list[list[Mapping[str, Any]]] = []
    for char in sorted(chars, key=lambda item: (float(item["top"]), float(item["x0"]))):
        if not lines or abs(float(char["top"]) - float(lines[-1][0]["top"])) > 2:
            lines.append([char])
        else:
            lines[-1].append(char)

    rectangles: list[tuple[float, float, float, float]] = []
    for line in lines:
        left = min(float(char["x0"]) for char in line)
        right = max(float(char["x1"]) for char in line)
        top = min(float(char["top"]) for char in line)
        bottom = max(float(char["bottom"]) for char in line)
        rectangles.append((left, page_height - bottom, right, page_height - top))
    return tuple(rectangles)


def _placements_for_match(
    document: PDF,
    match: RenderedMatch,
) -> tuple[PdfAnnotationPlacement, ...]:
    placements: list[PdfAnnotationPlacement] = []
    pages = sorted({page for page, _ in match.page_chars})
    for page_number in pages:
        chars = [char for page, char in match.page_chars if page == page_number]
        page_height = float(document.pages[page_number - 1].height)
        rectangles = _line_rectangles(chars, page_height)
        placements.append(
            PdfAnnotationPlacement(
                page=page_number,
                rectangles=rectangles,
                note_top=max(rectangle[3] for rectangle in rectangles),
            )
        )
    return tuple(placements)


def _resolve_replacement(
    document: PDF,
    change: TextReplaceChange,
    regions: Sequence[SyncTexRegion],
) -> PdfAnnotationResult:
    search_text = latex_to_visible_text(change.new_text)
    pages = sorted({region.page for region in regions})
    matches = _find_rendered_matches(document, pages, search_text)
    matching_regions: list[RenderedMatch] = []
    for match in matches:
        matched_pages = {page for page, _ in match.page_chars}
        if all(
            any(
                _intersects(char, region)
                for char_page, char in match.page_chars
                for region in regions
                if char_page == page and region.page == page
            )
            for page in matched_pages
        ):
            matching_regions.append(match)

    if len(matching_regions) != 1:
        raise PdfAnnotationError(
            f"Rendered text {search_text!r} matched {len(matching_regions)} times in "
            "SyncTeX candidate regions."
        )
    return PdfAnnotationResult(
        kind="replace",
        search_text=search_text,
        placements=_placements_for_match(document, matching_regions[0]),
    )


def _anchor_quote(value: str, *, suffix: bool) -> str | None:
    if not value.strip():
        return None
    visible = latex_to_visible_text(value)
    if len(visible) <= _ANCHOR_LIMIT:
        return visible
    if suffix:
        shortened = visible[-_ANCHOR_LIMIT:]
        separator = shortened.find(" ")
        return shortened[separator + 1 :] if separator >= 0 else shortened
    shortened = visible[:_ANCHOR_LIMIT]
    separator = shortened.rfind(" ")
    return shortened[:separator] if separator >= 0 else shortened


def _unique_anchor(
    document: PDF,
    pages: Sequence[int],
    quote: str,
    name: str,
) -> RenderedMatch:
    matches = _find_rendered_matches(document, pages, quote)
    if len(matches) != 1:
        raise PdfAnnotationError(
            f"Rendered {name} anchor {quote!r} matched {len(matches)} times on "
            "SyncTeX candidate pages."
        )
    return matches[0]


def _resolve_deletion(
    document: PDF,
    change: TextDeleteChange,
    regions: Sequence[SyncTexRegion],
) -> PdfAnnotationResult:
    # TODO(schema > 1): Consider explicit rendered_before_context and
    # rendered_after_context fields for deletion anchors involving macro expansion.
    pages = sorted({region.page for region in regions})
    before_quote = _anchor_quote(change.before_context, suffix=True)
    after_quote = _anchor_quote(change.after_context, suffix=False)
    if before_quote is None and after_quote is None:
        raise PdfAnnotationError("A deletion needs visible before_context or after_context.")

    before_match = (
        _unique_anchor(document, pages, before_quote, "before_context")
        if before_quote is not None
        else None
    )
    after_match = (
        _unique_anchor(document, pages, after_quote, "after_context")
        if after_quote is not None
        else None
    )
    if (
        before_match is not None
        and after_match is not None
        and before_match.end_index > after_match.start_index
    ):
        raise PdfAnnotationError("Deletion anchors occur in the wrong rendered order.")

    anchor_match = after_match or before_match
    assert anchor_match is not None
    anchor_page, anchor_char = (
        anchor_match.page_chars[0] if after_match is not None else anchor_match.page_chars[-1]
    )
    page_height = float(document.pages[anchor_page - 1].height)
    note_top = page_height - float(anchor_char["top"])
    return PdfAnnotationResult(
        kind="delete",
        search_text=None,
        placements=(PdfAnnotationPlacement(page=anchor_page, rectangles=(), note_top=note_top),),
    )


def _comment(spec: MutationSpec) -> str:
    change = spec.change
    header = f"FaultTeX mutation: {spec.id}\nLabel: {spec.label}\nTarget: {change.file}\n\n"
    if isinstance(change, TextReplaceChange):
        detail = f"Original LaTeX:\n{change.old_text}\n\nMutated LaTeX:\n{change.new_text}\n\n"
    else:
        detail = f"Deleted LaTeX:\n{change.text}\n\n"
    return header + detail + f"Description:\n{spec.description}"


def _add_note(
    writer: PdfWriter,
    placement: PdfAnnotationPlacement,
    spec: MutationSpec,
    comment: str,
    name: str,
    color: tuple[float, float, float],
) -> None:
    page_index = placement.page - 1
    page = writer.pages[page_index]
    page_right = float(page.mediabox.right)
    page_bottom = float(page.mediabox.bottom)
    page_top = float(page.mediabox.top)
    note_left = page_right - 24
    note_bottom = min(max(page_bottom + 4, placement.note_top - 16), page_top - 20)
    note = Text(
        rect=(note_left, note_bottom, note_left + 16, note_bottom + 16),
        text=comment,
        open=False,
        title_bar="FaultTeX",
    )
    note[NameObject("/Subj")] = TextStringObject(spec.label)
    note[NameObject("/NM")] = TextStringObject(name)
    note[NameObject("/C")] = ArrayObject([FloatObject(component) for component in color])
    note[NameObject("/Name")] = NameObject("/Comment")
    writer.add_annotation(page_number=page_index, annotation=note)


def _add_annotations(
    writer: PdfWriter,
    result: PdfAnnotationResult,
    spec: MutationSpec,
) -> tuple[tuple[int, str, str], ...]:
    expectations: list[tuple[int, str, str]] = []
    comment = _comment(spec)
    if result.kind == "replace":
        for placement in result.placements:
            page_index = placement.page - 1
            left = min(rectangle[0] for rectangle in placement.rectangles)
            bottom = min(rectangle[1] for rectangle in placement.rectangles)
            right = max(rectangle[2] for rectangle in placement.rectangles)
            top = max(rectangle[3] for rectangle in placement.rectangles)
            quad_values: list[float] = []
            for x0, y0, x1, y1 in placement.rectangles:
                quad_values.extend((x0, y0, x1, y0, x0, y1, x1, y1))

            highlight_name = f"faulttex-{spec.id}-highlight-p{placement.page}"
            highlight = Highlight(
                rect=(left, bottom, right, top),
                quad_points=ArrayObject([FloatObject(value) for value in quad_values]),
                highlight_color="69d36f",
                printing=True,
                title_bar="FaultTeX",
            )
            highlight[NameObject("/Contents")] = TextStringObject(comment)
            highlight[NameObject("/Subj")] = TextStringObject(spec.label)
            highlight[NameObject("/NM")] = TextStringObject(highlight_name)
            highlight[NameObject("/CA")] = FloatObject(0.45)
            writer.add_annotation(page_number=page_index, annotation=highlight)
            expectations.append((placement.page, "/Highlight", highlight_name))

            note_name = f"faulttex-{spec.id}-note-p{placement.page}"
            _add_note(writer, placement, spec, comment, note_name, (0.41, 0.83, 0.44))
            expectations.append((placement.page, "/Text", note_name))
    else:
        placement = result.placements[0]
        note_name = f"faulttex-{spec.id}-delete-p{placement.page}"
        _add_note(writer, placement, spec, comment, note_name, (0.9, 0.2, 0.2))
        expectations.append((placement.page, "/Text", note_name))
    return tuple(expectations)


def _page_text(path: Path) -> tuple[str, ...]:
    with pdfplumber.open(path) as document:
        return tuple(page.extract_text() or "" for page in document.pages)


def _page_sizes(reader: PdfReader) -> tuple[tuple[float, float], ...]:
    return tuple((float(page.mediabox.width), float(page.mediabox.height)) for page in reader.pages)


def _verify_pdf(
    original: Path,
    annotated: Path,
    expectations: Sequence[tuple[int, str, str]],
) -> None:
    original_reader = PdfReader(original)
    annotated_reader = PdfReader(annotated)
    if _page_sizes(original_reader) != _page_sizes(annotated_reader):
        raise PdfAnnotationError("PDF page count or dimensions changed during annotation.")
    if _page_text(original) != _page_text(annotated):
        raise PdfAnnotationError("PDF text content changed during annotation.")

    found: set[tuple[int, str, str]] = set()
    for page_number, page in enumerate(annotated_reader.pages, 1):
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            name = str(annotation.get("/NM", ""))
            if name.startswith("faulttex-"):
                found.add((page_number, str(annotation.get("/Subtype", "")), name))
                if not str(annotation.get("/Contents", "")):
                    raise PdfAnnotationError(f"Annotation {name} has no comment content.")
    if found != set(expectations):
        raise PdfAnnotationError(
            f"Embedded annotations did not match expectations: expected {expectations}, found {found}."
        )


def annotate_mutation_pdf(
    applied: AppliedChange,
    spec: MutationSpec,
    pdf: Path,
) -> PdfAnnotationResult:
    """Atomically add and verify native PDF annotations for one applied mutation."""
    project = applied.inspection.project.resolve(strict=True)
    pdf = pdf.resolve(strict=True)
    if not pdf.is_relative_to(project):
        raise PdfAnnotationError("The compiled PDF must be inside the mutated project.")

    temporary = pdf.with_name(f".{pdf.name}.annotated.tmp")
    try:
        regions = _synctex_regions(applied, pdf)
        with pdfplumber.open(pdf) as document:
            if isinstance(spec.change, TextReplaceChange):
                result = _resolve_replacement(document, spec.change, regions)
            else:
                result = _resolve_deletion(document, spec.change, regions)

        reader = PdfReader(pdf)
        writer = PdfWriter()
        writer.pdf_header = reader.pdf_header
        writer.clone_document_from_reader(reader)
        expectations = _add_annotations(writer, result, spec)
        with temporary.open("wb") as stream:
            writer.write(stream)
        _verify_pdf(pdf, temporary, expectations)
        temporary.replace(pdf)
        return result
    except PdfAnnotationError:
        temporary.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise PdfAnnotationError(f"Could not annotate PDF {pdf}: {exc}") from exc
