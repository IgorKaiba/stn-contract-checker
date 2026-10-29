"""A1 Ingestor: байты -> Document с абзацами и смещениями.

Абзац = блок текста, разделённый пустой строкой. Смещения считаются от
нормализованного текста (только перевод строк \r\n -> \n), сам текст не меняется.
"""
from __future__ import annotations

import hashlib
import re

from .models import Document, Evidence, Paragraph

_PARA_SEP = re.compile(r"\n[ \t]*\n+")


def decode(raw: bytes) -> tuple[str, str | None]:
    try:
        return raw.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return raw.decode("cp1251", errors="replace"), "файл не в UTF-8, прочитан как cp1251"


def split_paragraphs(text: str) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    pos = 0
    bounds = []
    for m in _PARA_SEP.finditer(text):
        bounds.append((pos, m.start()))
        pos = m.end()
    bounds.append((pos, len(text)))
    n = 0
    for start, end in bounds:
        chunk = text[start:end]
        if not chunk.strip():
            continue
        lead = len(chunk) - len(chunk.lstrip())
        trail = len(chunk) - len(chunk.rstrip())
        s, e = start + lead, end - trail
        n += 1
        paragraphs.append(Paragraph(pid=f"p-{n}", start=s, end=e, text=text[s:e]))
    return paragraphs


def make_document(file_name: str, raw: bytes) -> Document:
    text, note = decode(raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    doc_id = hashlib.sha1(file_name.encode("utf-8") + b"\0" + text.encode("utf-8")).hexdigest()[:10]
    return Document(doc_id=doc_id, file_name=file_name, text=text,
                    paragraphs=split_paragraphs(text), encoding_note=note)


def evidence(doc: Document, start: int, end: int) -> Evidence:
    """Основание = точный срез исходного текста + абзац, в котором он начинается."""
    pid = doc.paragraphs[0].pid if doc.paragraphs else "p-1"
    for p in doc.paragraphs:
        if p.start <= start < p.end or (start == end == p.end):
            pid = p.pid
            break
    return Evidence(doc_id=doc.doc_id, file_name=doc.file_name, pid=pid,
                    quote=doc.text[start:end], start=start, end=end)
