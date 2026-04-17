from __future__ import annotations

from io import BytesIO
from pathlib import Path
import os
import re

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer


INLINE_CODE_RE = re.compile(r"`([^`]+)`")
ORDERED_LIST_PATTERN = re.compile(r"^\d+\.\s+(.+)$")
INLINE_PATTERN = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")
READABLE_TITLE_PATTERN = re.compile(r"^#\s+(?:Читабельный текст|Readable text)\s*$", re.IGNORECASE)
READABLE_SECTION_PATTERN = re.compile(r"^##\s+(?:Текст|Text)\s*$", re.IGNORECASE)
READABLE_META_PATTERN = re.compile(
    r"^-\s*(?P<label>Файл|File|Модель|Model|Язык|Language|Создано|Created):\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
_REGISTERED_FONT_NAMES: tuple[str, str] | None = None
LINE_HEIGHT_FACTORS = {
    "compact": 1.32,
    "normal": 1.42,
    "relaxed": 1.56,
}


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _ensure_pdf_fonts() -> tuple[str, str]:
    global _REGISTERED_FONT_NAMES
    if _REGISTERED_FONT_NAMES is not None:
        return _REGISTERED_FONT_NAMES

    windows_fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    normal_path = _first_existing(
        [
            windows_fonts_dir / "segoeui.ttf",
            windows_fonts_dir / "arial.ttf",
            windows_fonts_dir / "calibri.ttf",
        ]
    )
    bold_path = _first_existing(
        [
            windows_fonts_dir / "segoeuib.ttf",
            windows_fonts_dir / "arialbd.ttf",
            windows_fonts_dir / "calibrib.ttf",
        ]
    )

    if normal_path is None:
        _REGISTERED_FONT_NAMES = ("Helvetica", "Helvetica-Bold")
        return _REGISTERED_FONT_NAMES

    normal_name = "VoctariumUIFont"
    if normal_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(normal_name, str(normal_path)))

    if bold_path is not None:
        bold_name = "VoctariumUIFontBold"
        if bold_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
    else:
        bold_name = normal_name

    _REGISTERED_FONT_NAMES = (normal_name, bold_name)
    return _REGISTERED_FONT_NAMES


def _normalize_font_size_px(value: int | float | None) -> int:
    size = int(value or 18)
    return max(12, min(32, size))


def _normalize_line_height_mode(value: str | None) -> str:
    if value in LINE_HEIGHT_FACTORS:
        return str(value)
    return "normal"


def _normalize_align_mode(value: str | None) -> str:
    if value in {"left", "justify", "justify_hyphen"}:
        return str(value)
    return "justify"


def _normalize_content_width_percent(value: int | float | None) -> int:
    percent = int(value or 100)
    return max(50, min(100, percent))


def _strip_inline_markdown(text: str) -> str:
    cleaned = INLINE_CODE_RE.sub(r"\1", str(text).strip())
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    return cleaned.strip().strip("`").strip()


def _body_alignment(align_mode: str) -> int:
    return TA_LEFT if align_mode == "left" else TA_JUSTIFY


def _page_side_margin_mm(content_width_percent: int) -> float:
    extra_margin = ((100 - content_width_percent) / 50.0) * 8.0
    return 10.0 + max(0.0, extra_margin)


def prepare_readable_markdown_for_pdf(markdown_text: str, *, fallback_title: str | None = None) -> tuple[str, str]:
    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1

    start_index = index
    title_found = False
    metadata_count = 0
    text_heading_found = False
    document_title = _strip_inline_markdown(fallback_title or "") or "Voctarium"
    pending_title = document_title

    if index < len(lines) and READABLE_TITLE_PATTERN.match(lines[index].strip()):
        title_found = True
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1

    metadata_index = index
    while metadata_index < len(lines):
        match = READABLE_META_PATTERN.match(lines[metadata_index].strip())
        if not match:
            break
        metadata_count += 1
        label = match.group("label").strip().lower()
        value = _strip_inline_markdown(match.group("value"))
        if label in {"файл", "file"} and value:
            pending_title = value
        metadata_index += 1

    if metadata_count:
        index = metadata_index
        while index < len(lines) and not lines[index].strip():
            index += 1

    if index < len(lines) and READABLE_SECTION_PATTERN.match(lines[index].strip()):
        text_heading_found = True
        index += 1
        while index < len(lines) and not lines[index].strip():
            index += 1

    scaffold_detected = title_found or text_heading_found or metadata_count >= 2
    if scaffold_detected:
        document_title = pending_title or document_title
        body_lines = lines[index:]
    else:
        body_lines = lines[start_index:]
        if body_lines and READABLE_TITLE_PATTERN.match(body_lines[0].strip()):
            body_lines = body_lines[1:]
            while body_lines and not body_lines[0].strip():
                body_lines = body_lines[1:]

    body_text = "\n".join(body_lines).strip()
    return document_title or "Voctarium", body_text


def _make_styles(
    *,
    font_size_px: int = 18,
    line_height_mode: str = "normal",
    align_mode: str = "justify",
) -> StyleSheet1:
    normal_font, bold_font = _ensure_pdf_fonts()
    styles = getSampleStyleSheet()
    body_font_size = round(_normalize_font_size_px(font_size_px) * 0.75, 2)
    line_factor = LINE_HEIGHT_FACTORS[_normalize_line_height_mode(line_height_mode)]
    body_leading = round(body_font_size * line_factor, 2)
    body_alignment = _body_alignment(_normalize_align_mode(align_mode))
    meta_font_size = max(9.5, round(body_font_size * 0.92, 2))
    heading_font_size = round(body_font_size * 1.14, 2)
    subheading_font_size = round(body_font_size * 1.05, 2)
    title_font_size = min(18.0, round(body_font_size * 1.22, 2))

    styles.add(
        ParagraphStyle(
            name="VoctariumTitle",
            parent=styles["Heading1"],
            fontName=bold_font,
            fontSize=title_font_size,
            leading=round(title_font_size * 1.14, 2),
            alignment=TA_CENTER,
            spaceAfter=4.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="VoctariumHeading",
            parent=styles["Heading2"],
            fontName=bold_font,
            fontSize=heading_font_size,
            leading=round(heading_font_size * 1.18, 2),
            alignment=TA_LEFT,
            spaceBefore=3 * mm,
            spaceAfter=2.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="VoctariumSubheading",
            parent=styles["Heading3"],
            fontName=bold_font,
            fontSize=subheading_font_size,
            leading=round(subheading_font_size * 1.18, 2),
            alignment=TA_LEFT,
            spaceBefore=2.5 * mm,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="VoctariumBody",
            parent=styles["BodyText"],
            fontName=normal_font,
            fontSize=body_font_size,
            leading=body_leading,
            alignment=body_alignment,
            firstLineIndent=8 * mm,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="VoctariumMeta",
            parent=styles["BodyText"],
            fontName=normal_font,
            fontSize=meta_font_size,
            leading=round(meta_font_size * 1.28, 2),
            alignment=TA_LEFT,
            firstLineIndent=0,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="VoctariumEmpty",
            parent=styles["BodyText"],
            fontName=normal_font,
            fontSize=body_font_size,
            leading=body_leading,
            alignment=TA_LEFT,
            firstLineIndent=0,
            spaceAfter=0,
        )
    )
    return styles


def _render_inline_markup(text: str) -> str:
    cleaned = INLINE_CODE_RE.sub(r"\1", text.strip())
    parts: list[str] = []
    position = 0
    for match in INLINE_PATTERN.finditer(cleaned):
        if match.start() > position:
            parts.append(
                cleaned[position:match.start()].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
        token = match.group(0)
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            inner = token[2:-2].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"<b>{inner}</b>")
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            inner = token[1:-1].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"<i>{inner}</i>")
        else:
            parts.append(token.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        position = match.end()
    if position < len(cleaned):
        parts.append(cleaned[position:].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    rendered = "".join(parts)
    if rendered.startswith("_") and rendered.endswith("_") and len(rendered) > 2:
        inner = rendered[1:-1].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<i>{inner}</i>"
    return rendered


def _parse_markdown_blocks(markdown_text: str) -> list[tuple[str, str | list[str]]]:
    blocks: list[tuple[str, str | list[str]]] = []
    paragraph_lines: list[str] = []
    list_lines: list[str] = []
    list_kind: str | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            blocks.append(("paragraph", " ".join(part.strip() for part in paragraph_lines if part.strip())))
            paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_lines, list_kind
        if list_lines and list_kind:
            blocks.append((list_kind, list_lines[:]))
        list_lines = []
        list_kind = None

    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            flush_list()
            blocks.append(("heading", stripped[2:].strip()))
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(("heading", stripped[3:].strip()))
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            flush_list()
            blocks.append(("subheading", stripped[4:].strip()))
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if list_kind not in (None, "list"):
                flush_list()
            list_kind = "list"
            list_lines.append(stripped[2:].strip())
            continue

        ordered_match = ORDERED_LIST_PATTERN.match(stripped)
        if ordered_match:
            flush_paragraph()
            if list_kind not in (None, "olist"):
                flush_list()
            list_kind = "olist"
            list_lines.append(ordered_match.group(1).strip())
            continue

        flush_list()
        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_list()
    return blocks


def render_markdown_pdf(
    markdown_text: str,
    *,
    fallback_title: str | None = None,
    font_size_px: int = 18,
    line_height_mode: str = "normal",
    align_mode: str = "justify",
    paragraph_gap: bool = False,
    content_width_percent: int = 100,
) -> bytes:
    document_title, document_body = prepare_readable_markdown_for_pdf(markdown_text, fallback_title=fallback_title)
    styles = _make_styles(
        font_size_px=font_size_px,
        line_height_mode=line_height_mode,
        align_mode=align_mode,
    )
    story = []
    if document_title:
        story.append(Paragraph(_render_inline_markup(document_title), styles["VoctariumTitle"]))
    blocks = _parse_markdown_blocks(document_body)
    paragraph_spacing_mm = 4.8 if paragraph_gap else 2.2

    for index, (block_type, payload) in enumerate(blocks):
        if block_type == "heading":
            if story:
                story.append(Spacer(1, 1.0 * mm))
            story.append(Paragraph(_render_inline_markup(str(payload)), styles["VoctariumHeading"]))
            continue

        if block_type == "subheading":
            if story:
                story.append(Spacer(1, 0.9 * mm))
            story.append(Paragraph(_render_inline_markup(str(payload)), styles["VoctariumSubheading"]))
            continue

        if block_type in {"list", "olist"}:
            items = [
                ListItem(Paragraph(_render_inline_markup(item), styles["VoctariumMeta"]), leftIndent=0)
                for item in list(payload)
            ]
            story.append(
                ListFlowable(
                    items,
                    bulletType="bullet" if block_type == "list" else "1",
                    leftIndent=4 * mm,
                )
            )
            story.append(Spacer(1, 1.6 * mm))
            continue

        paragraph_text = _render_inline_markup(str(payload))
        style_name = "VoctariumBody"
        if paragraph_text.startswith("<i>") and paragraph_text.endswith("</i>"):
            style_name = "VoctariumEmpty"
        story.append(Paragraph(paragraph_text, styles[style_name]))
        if index < len(blocks) - 1:
            story.append(Spacer(1, paragraph_spacing_mm * mm))

    if not story:
        story.append(Paragraph("No content.", styles["VoctariumEmpty"]))

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=_page_side_margin_mm(_normalize_content_width_percent(content_width_percent)) * mm,
        rightMargin=_page_side_margin_mm(_normalize_content_width_percent(content_width_percent)) * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Voctarium Export",
    )
    document.build(story)
    return output.getvalue()
