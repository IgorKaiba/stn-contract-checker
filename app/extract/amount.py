"""A4: сумма договора в рублях."""
from __future__ import annotations

from ..ingest import evidence
from ..models import Candidate, Document
from ..textutil import money_in
from .common import clause_lines, clause_sentences, has_any
from .registry import register

_CANDIDATE = ("стоимост", "цена", "цену")
_QUALIFIER = ("общ", "итогов", "договор")
_EXCLUDE = ("аванс", "лимит", "не является", "предоплат", "бюджет")
_NO_DATA = ("не указан", "определяется спецификацией", "приложени")


@register("amount", "Сумма")
def extract_amount(doc: Document, region: tuple[int, int]) -> list[Candidate]:
    out: list[Candidate] = []
    for clause in clause_lines(doc, region):
        if not (has_any(clause.text, _CANDIDATE) and has_any(clause.text, _QUALIFIER)):
            continue
        found = False
        for s in clause_sentences(doc, clause):
            if has_any(s.text, _EXCLUDE):
                continue
            values = money_in(s.text)
            if values and has_any(s.text, _CANDIDATE):
                for v in values:
                    out.append(Candidate("amount", v, evidence(doc, s.start, s.end)))
                    found = True
        if not found and has_any(clause.text, _NO_DATA) and not money_in(clause.text):
            out.append(Candidate("amount", None, evidence(doc, clause.start, clause.end), no_data=True))
    return out
