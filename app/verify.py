"""A6 Verifier (рантайм): инварианты результата. Нарушение -> «требует проверки»."""
from __future__ import annotations

from datetime import date

from .models import ContractCard, DocType, Document, FieldValue, Signed, State


def _fail(fv: FieldValue, code: str) -> None:
    fv.state = State.NEEDS_REVIEW
    fv.reason = f"нарушен инвариант {code}" + (f"; {fv.reason}" if fv.reason else "")


def verify_card(card: ContractCard, docs: dict[str, Document]) -> None:
    for fv in card.fields():
        for ev in fv.evidence + fv.base_evidence:                       # V1
            d = docs.get(ev.doc_id)
            if d is None or d.text[ev.start:ev.end] != ev.quote:
                _fail(fv, "V1 (цитата не совпадает с источником)")
                break
        if fv.state in (State.OK, State.CHANGED) and (fv.value is None or not fv.evidence):
            _fail(fv, "V2 (значение без основания)")
        if fv.state == State.NO_DATA and fv.value is not None:
            _fail(fv, "V3"); fv.value = None
        if fv.state == State.CHANGED:                                    # V4
            src = docs.get(fv.changed_by or "")
            if not src or src.doc_type != DocType.AMENDMENT or src.signed != Signed.SIGNED_BOTH:
                _fail(fv, "V4 (изменение не подтверждено подписанным ДС)")
        if fv.state in (State.OK, State.CHANGED):                        # V5
            if fv.field == "amount" and not (isinstance(fv.value, int) and fv.value > 0):
                _fail(fv, "V5")
            if fv.field == "term" and not isinstance(fv.value, date):
                _fail(fv, "V5")
