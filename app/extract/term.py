"""A4: срок поставки."""
from __future__ import annotations

import re

from ..ingest import evidence
from ..models import Candidate, Document
from ..textutil import dates_in
from .common import clause_lines, clause_sentences, has_any
from .registry import register

_SUPPLY = ("постав",)
_DEADLINE = re.compile(r"не\s+позднее|\bдо\b|\bсрок", re.IGNORECASE)
_EXCLUDE = ("оплат", "платеж", "платёж", "приемк", "приёмк", "не изменяет срок", "а не поставки")


@register("term", "Срок поставки")
def extract_term(doc: Document, region: tuple[int, int]) -> list[Candidate]:
    out: list[Candidate] = []
    for clause in clause_lines(doc, region):
        for s in clause_sentences(doc, clause):
            if not has_any(s.text, _SUPPLY) or not _DEADLINE.search(s.text):
                continue
            if has_any(s.text, _EXCLUDE):
                continue
            for d in dates_in(s.text):
                out.append(Candidate("term", d, evidence(doc, s.start, s.end)))
    return out
