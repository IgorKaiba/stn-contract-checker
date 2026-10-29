"""Разбор изменений: новая редакция пункта в кавычках и прямые формулировки изменения.

change sentences: «изменить … на X», «перенести срок поставки с D1 на D2».
"""
from __future__ import annotations

import re

from ..ingest import evidence
from ..models import Candidate, Document
from ..textutil import MONEY_RE, dates_in, money_in
from .common import body_region, clause_lines, clause_sentences, has_any
from .registry import REGISTRY

_REWRITE = re.compile(r"[Пп]ункт\w*\s+(\d+(?:\.\d+)*)[^\n«]*?(?:изложить|читать)\s+в\s+(?:следующей|новой)\s+редакции\s*:?\s*«")
_CHANGE_VERB = re.compile(r"измени|перенест|перенос|установить", re.IGNORECASE)
_PROPOSAL_VERB = re.compile(r"предлага|просим", re.IGNORECASE)


def _closing_quote(text: str, open_pos: int) -> int | None:
    """Позиция парной закрывающей «» с учётом вложенных кавычек."""
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "«":
            depth += 1
        elif text[i] == "»":
            depth -= 1
            if depth == 0:
                return i
    return None


def rewrites(doc: Document) -> list[tuple[str, tuple[int, int]]]:
    out = []
    for m in _REWRITE.finditer(doc.text):
        open_pos = m.end() - 1
        close = _closing_quote(doc.text, open_pos)
        if close is not None:
            out.append((m.group(1), (open_pos + 1, close)))
    return out


def change_candidates(doc: Document, allow_proposal_wording: bool) -> list[Candidate]:
    """Все изменяемые значения в документе: новые редакции пунктов + прямые формулировки."""
    out: list[Candidate] = []
    rewrite_regions = rewrites(doc)
    for _clause_no, region in rewrite_regions:
        for extractor in REGISTRY.values():
            out.extend(c for c in extractor(doc, region) if not c.no_data)
    covered = [r for _, r in rewrite_regions]
    for clause in clause_lines(doc, body_region(doc)):
        for s in clause_sentences(doc, clause):
            if any(a <= s.start < b for a, b in covered):
                continue
            if not _CHANGE_VERB.search(s.text):
                continue
            if _PROPOSAL_VERB.search(s.text) and not allow_proposal_wording:
                continue
            low = s.text.lower()
            if "стоимост" in low and money_in(s.text):
                m = list(MONEY_RE.finditer(s.text))[-1]
                out.append(Candidate("amount", int(re.sub(r"\D", "", m.group(1))), evidence(doc, s.start, s.end)))
            if "срок" in low and "постав" in low and dates_in(s.text):
                out.append(Candidate("term", dates_in(s.text)[-1], evidence(doc, s.start, s.end)))
    return out
