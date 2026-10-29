"""A5 Resolver: действующие условия на дату проверки.

Правило задания: условия изменяет только допсоглашение, подписанное обеими
сторонами и вступившее в силу к дате проверки. Проекты, письма и ДС, ещё не
вступившие в силу, — предложения (Proposal), значения не меняют.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .extract import REGISTRY
from .extract.amendments import change_candidates
from .extract.common import body_region
from .link import Links, link, party_mismatch
from .models import (Candidate, ContractCard, DocType, Document, FieldValue, Proposal,
                     ProposalKind, Signed, State)
from .ingest import evidence
from .verify import verify_card
from . import llm_fallback


@dataclass
class Analysis:
    check_date: date
    cards: list[ContractCard]
    docs: dict[str, Document]
    links: Links
    notes: list[str] = field(default_factory=list)


def _from_candidates(field_name: str, cands: list[Candidate]) -> FieldValue:
    values = [c for c in cands if not c.no_data]
    distinct = {c.value for c in values}
    if len(distinct) == 1:
        return FieldValue(field_name, values[0].value, State.OK, [values[0].evidence])
    if len(distinct) > 1:
        return FieldValue(field_name, None, State.NEEDS_REVIEW, [c.evidence for c in values],
                          reason="в документе несколько разных значений")
    nd = [c.evidence for c in cands if c.no_data]
    return FieldValue(field_name, None, State.NO_DATA, nd,
                      reason=None if nd else "соответствующий пункт в тексте не найден")


def _supplier_field(doc: Document) -> FieldValue:
    if not doc.supplier:
        return FieldValue("supplier", None, State.NO_DATA, reason="поставщик в тексте не указан")
    idx = doc.text.find(doc.supplier)
    return FieldValue("supplier", doc.supplier, State.OK, [evidence(doc, idx, idx + len(doc.supplier))])


def _status_of(doc: Document, check: date) -> tuple[str, str | None]:
    """'apply' | 'proposal:<kind>' | 'review' + причина."""
    if doc.doc_type == DocType.DRAFT:
        return "proposal:" + ProposalKind.DRAFT.value, None
    if doc.doc_type == DocType.LETTER:
        return "proposal:" + ProposalKind.LETTER.value, None
    # AMENDMENT
    if doc.signed == Signed.NOT_SIGNED:
        return "proposal:" + ProposalKind.DRAFT.value, None
    if doc.signed == Signed.UNKNOWN:
        return "review", f"{doc.file_name}: статус подписания допсоглашения не определён"
    if doc.effective_date is None:
        return "review", f"{doc.file_name}: в допсоглашении не указана дата вступления в силу"
    if doc.sign_date and doc.sign_date > check:
        return "proposal:" + ProposalKind.SIGNED_NOT_YET_EFFECTIVE.value, None
    if doc.effective_date > check:
        return "proposal:" + ProposalKind.SIGNED_NOT_YET_EFFECTIVE.value, None
    return "apply", None


def build_card(contract: Document, related: list[Document], check: date, warnings: list[str]) -> ContractCard:
    region = body_region(contract)
    base = {f: _from_candidates(f, fn(contract, region)) for f, fn in REGISTRY.items()}
    for f, fv in base.items():
        if fv.state == State.NO_DATA and not fv.evidence:      # пункт не найден правилами
            hint = llm_fallback.suggest(contract, f)
            if hint:
                base[f] = FieldValue(f, hint.value, State.NEEDS_REVIEW, [hint.evidence],
                                     reason="значение найдено локальной моделью, подтвердите по цитате")
    card = ContractCard(contract.contract_no, contract.doc_id, _supplier_field(contract),
                        base["amount"], base["term"], related_docs=[d.doc_id for d in related],
                        warnings=list(warnings))
    if contract.signed != Signed.SIGNED_BOTH:
        card.warnings.append(f"{contract.file_name}: в тексте не подтверждено подписание договора обеими сторонами")

    applicable: dict[str, list[tuple[tuple, Candidate, Document]]] = {}
    for d in related:
        status, reason = _status_of(d, check)
        cands = change_candidates(d, allow_proposal_wording=status != "apply")
        if status == "apply" and party_mismatch(d, contract):
            status, reason = "review", f"{d.file_name}: стороны допсоглашения не совпадают с договором"
        for c in cands:
            if status == "apply":
                key = (d.effective_date, d.doc_date or d.effective_date)
                applicable.setdefault(c.field, []).append((key, c, d))
            elif status.startswith("proposal:"):
                card.proposals.append(Proposal(contract.contract_no, c.field, c.value, d.doc_id,
                                               ProposalKind(status.split(":", 1)[1]), [c.evidence]))
            else:
                fv = getattr(card, c.field)
                fv.state, fv.reason = State.NEEDS_REVIEW, reason
                fv.evidence = fv.evidence + [c.evidence]
        if status == "review" and not cands:
            card.warnings.append(reason)

    for field_name, changes in applicable.items():
        fv: FieldValue = getattr(card, field_name)
        if fv.state == State.NEEDS_REVIEW and fv.reason and "допсоглашени" in fv.reason:
            continue
        changes.sort(key=lambda t: t[0])
        last_key = changes[-1][0]
        last = [t for t in changes if t[0] == last_key]
        if len({t[1].value for t in last}) > 1:
            fv.state, fv.reason = State.NEEDS_REVIEW, "допсоглашения с одной датой задают разные значения"
            fv.evidence = [t[1].evidence for t in last]
            continue
        _, cand, doc = changes[-1]
        new = FieldValue(field_name, cand.value, State.CHANGED, [cand.evidence], changed_by=doc.doc_id,
                         base_value=fv.value, base_evidence=fv.evidence,
                         reason=None if fv.state in (State.OK, State.NO_DATA) else f"исходное значение: {fv.reason}")
        setattr(card, field_name, new)
    return card


def analyze(docs: list[Document], check: date) -> Analysis:
    lk = link(docs)
    cards = []
    for no, contract in sorted(lk.contracts.items()):
        card = build_card(contract, lk.related.get(no, []), check, lk.warnings.get(no, []))
        if no in lk.duplicates:
            for fv in card.fields():
                fv.state, fv.reason = State.NEEDS_REVIEW, "загружено несколько договоров с этим номером"
            card.warnings.append("дубликаты договора: " + ", ".join(d.file_name for d in lk.duplicates[no]))
        verify_card(card, {d.doc_id: d for d in docs})
        cards.append(card)
    return Analysis(check, cards, {d.doc_id: d for d in docs}, lk)
