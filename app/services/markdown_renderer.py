"""Renders PyMuPDF text blocks as Markdown.

Lines set in a font clearly larger than the document's body text become
headings, and each text block becomes a paragraph. Deliberately minimal:
richer Markdown (lists, tables) costs far more CPU than the load test allows.
"""
from collections import Counter

HEADING_SIZE_RATIO = 1.2

Block = dict
Line = dict


def render_markdown(blocks: list[Block]) -> str:
    """Return the Markdown for ``blocks`` as produced by ``page.get_text("dict")["blocks"]``."""
    heading_min_size = _body_font_size(blocks) * HEADING_SIZE_RATIO
    paragraphs = (_render_block(block, heading_min_size) for block in blocks)
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _body_font_size(blocks: list[Block]) -> int:
    """The font size that covers the most characters, i.e. the size of the body text."""
    chars_by_size: Counter[int] = Counter()
    for block in blocks:
        for line in block["lines"]:
            for span in line["spans"]:
                chars_by_size[round(span["size"])] += len(span["text"])
    return chars_by_size.most_common(1)[0][0] if chars_by_size else 0


def _render_block(block: Block, heading_min_size: float) -> str:
    lines = (_render_line(line, heading_min_size) for line in block["lines"])
    return "\n".join(line for line in lines if line)


def _render_line(line: Line, heading_min_size: float) -> str:
    text = "".join(span["text"] for span in line["spans"]).strip()
    if text and max(span["size"] for span in line["spans"]) >= heading_min_size:
        return f"# {text}"
    return text
