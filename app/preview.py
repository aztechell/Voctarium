from __future__ import annotations

import html
import re


TIMECODE_PATTERN = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\s-\s(\d{2}:\d{2}:\d{2})\]\s*(.+)$")
ORDERED_LIST_PATTERN = re.compile(r"^\d+\.\s+(.+)$")
INLINE_PATTERN = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")


def render_inline_html(text: str) -> str:
    parts: list[str] = []
    position = 0
    for match in INLINE_PATTERN.finditer(text):
        if match.start() > position:
            parts.append(html.escape(text[position:match.start()]))
        token = match.group(0)
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            parts.append(f"<strong>{html.escape(token[2:-2])}</strong>")
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            parts.append(f"<em>{html.escape(token[1:-1])}</em>")
        else:
            parts.append(html.escape(token))
        position = match.end()
    if position < len(text):
        parts.append(html.escape(text[position:]))
    return "".join(parts)


def markdown_to_safe_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    parts: list[str] = ['<article class="md-preview">']
    paragraph: list[str] = []
    list_kind: str | None = None

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = " ".join(paragraph)
        parts.append(f"<p>{render_inline_html(joined)}</p>")
        paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind == "ul":
            parts.append("</ul>")
        elif list_kind == "ol":
            parts.append("</ol>")
        list_kind = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            close_list()
            continue

        timecode_match = TIMECODE_PATTERN.match(line)
        if timecode_match:
            flush_paragraph()
            close_list()
            start, end, text = timecode_match.groups()
            parts.append(
                "<p class=\"segment\">"
                f"<span class=\"segment-time\">[{html.escape(start)} - {html.escape(end)}]</span> "
                f"{render_inline_html(text)}"
                "</p>"
            )
            continue

        if line.startswith("# "):
            flush_paragraph()
            close_list()
            parts.append(f"<h1>{render_inline_html(line[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            flush_paragraph()
            close_list()
            parts.append(f"<h2>{render_inline_html(line[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            flush_paragraph()
            close_list()
            parts.append(f"<h3>{render_inline_html(line[4:].strip())}</h3>")
            continue
        if line.startswith("- "):
            flush_paragraph()
            if list_kind != "ul":
                close_list()
                parts.append("<ul>")
                list_kind = "ul"
            parts.append(f"<li>{render_inline_html(line[2:].strip())}</li>")
            continue

        ordered_match = ORDERED_LIST_PATTERN.match(line)
        if ordered_match:
            flush_paragraph()
            if list_kind != "ol":
                close_list()
                parts.append("<ol>")
                list_kind = "ol"
            parts.append(f"<li>{render_inline_html(ordered_match.group(1).strip())}</li>")
            continue

        close_list()
        paragraph.append(line)

    flush_paragraph()
    close_list()
    parts.append("</article>")
    return "\n".join(parts)
