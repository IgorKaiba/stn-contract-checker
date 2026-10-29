"""Четыре вопроса пользователя как параметризуемые запросы к результату анализа."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .models import ContractCard, FieldValue, Proposal, State
from .resolve import Analysis, analyze


@dataclass
class FieldAnswer:
    contract_no: str
    field: FieldValue | None
    proposals: list[Proposal]
    check_date: date
    found: bool = True


@dataclass
class DeadlineRow:
    card: ContractCard
    pending_term: list[Proposal]


@dataclass
class DeadlineAnswer:
    before: date
    check_date: date
    rows: list[DeadlineRow] = field(default_factory=list)
    undetermined: list[ContractCard] = field(default_factory=list)


def _card(a: Analysis, no: str) -> ContractCard | None:
    return next((c for c in a.cards if c.contract_no == no), None)


def field_on(a: Analysis, contract_no: str, field_name: str, on: date | None = None) -> FieldAnswer:
    """Q1–Q3: значение поля договора на дату (по умолчанию — дата проверки)."""
    if on and on != a.check_date:
        a = analyze(list(a.docs.values()), on)
    card = _card(a, contract_no)
    if not card:
        return FieldAnswer(contract_no, None, [], a.check_date, found=False)
    return FieldAnswer(contract_no, getattr(card, field_name),
                       [p for p in card.proposals if p.field == field_name], a.check_date)


def deadline_before(a: Analysis, before: date) -> DeadlineAnswer:
    """Q4: договоры со сроком поставки строго раньше даты + несогласованные изменения срока."""
    ans = DeadlineAnswer(before, a.check_date)
    for c in a.cards:
        if c.term.state in (State.OK, State.CHANGED) and c.term.value < before:
            ans.rows.append(DeadlineRow(c, [p for p in c.proposals if p.field == "term"]))
        elif c.term.state in (State.NO_DATA, State.NEEDS_REVIEW):
            ans.undetermined.append(c)
    return ans
