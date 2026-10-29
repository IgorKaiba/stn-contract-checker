from __future__ import annotations

from ..models import Document
from ..textutil import SERVICE_LINE, Span, lines, sentences


def body_region(doc: Document) -> tuple[int, int]:
    """Тело документа без первого абзаца-шапки (заголовок, дата, статус)."""
    if len(doc.paragraphs) > 1:
        return doc.paragraphs[1].start, len(doc.text)
    return 0, len(doc.text)


def clause_lines(doc: Document, region: tuple[int, int]) -> list[Span]:
    return [ln for ln in lines(doc.text, *region) if not SERVICE_LINE.match(ln.text)]


def clause_sentences(doc: Document, clause: Span) -> list[Span]:
    return sentences(doc.text, clause)


def has_any(text: str, words: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(w in low for w in words)
