"""ORACLE: ожидаемые результаты на учебном комплекте documents/.
Литералы допустимы только здесь (см. scripts/gate.py)."""
from datetime import date
from pathlib import Path

import pytest

from app.models import ProposalKind, State
from app.pipeline import run
from app.queries import deadline_before, field_on
from tests.helpers import card, contract

DOCS = Path(__file__).resolve().parents[2] / "documents"
CHECK = date(2026, 3, 10)


def files(mutate=None, rename=False):
    out = []
    for i, p in enumerate(sorted(DOCS.glob("*.txt"))):
        text = p.read_text(encoding="utf-8")
        if mutate:
            text = mutate(p.name, text)
        out.append((f"file_{(i * 7) % 6}.txt" if rename else p.name, text.encode("utf-8")))
    return out


@pytest.fixture(scope="module")
def a():
    return run(files(), CHECK)


def test_three_contracts(a):
    assert [c.contract_no for c in a.cards] == ["STN-101", "STN-102", "STN-103"]


def test_stn101_changed_by_signed_amendment(a):
    c = card(a, "STN-101")
    assert c.amount.value == 1_380_000 and c.amount.state == State.CHANGED and c.amount.base_value == 1_200_000
    assert c.term.value == date(2026, 4, 30) and c.term.state == State.CHANGED and c.term.base_value == date(2026, 4, 15)
    assert a.docs[c.term.changed_by].file_name == "02_amendment_signed.txt"
    props = {(p.field, p.proposed_value, p.kind) for p in c.proposals}
    assert props == {("amount", 1_450_000, ProposalKind.DRAFT), ("term", date(2026, 5, 10), ProposalKind.DRAFT)}


def test_stn102_not_advance_not_payment_date(a):
    c = card(a, "STN-102")
    assert c.amount.value == 840_000 and c.amount.state == State.OK
    assert c.term.value == date(2026, 3, 20) and c.term.state == State.OK
    assert [(p.field, p.proposed_value, p.kind) for p in c.proposals] == [("term", date(2026, 3, 27), ProposalKind.LETTER)]


def test_stn103_amount_no_data(a):
    c = card(a, "STN-103")
    assert c.amount.state == State.NO_DATA and c.amount.value is None
    assert "не указано" in c.amount.evidence[0].quote
    assert c.term.value == date(2026, 4, 30)


def test_questions(a):
    q1 = field_on(a, "STN-101", "term", CHECK)
    assert q1.field.value == date(2026, 4, 30)
    assert field_on(a, "STN-102", "amount").field.value == 840_000
    assert field_on(a, "STN-103", "amount").field.state == State.NO_DATA
    q4 = deadline_before(a, date(2026, 4, 1))
    assert [r.card.contract_no for r in q4.rows] == ["STN-102"]
    assert q4.rows[0].pending_term and q4.rows[0].pending_term[0].kind == ProposalKind.LETTER


def test_all_evidence_exact(a):
    for c in a.cards:
        for fv in c.fields():
            for ev in fv.evidence + fv.base_evidence:
                assert a.docs[ev.doc_id].text[ev.start:ev.end] == ev.quote
        for p in c.proposals:
            for ev in p.evidence:
                assert a.docs[ev.doc_id].text[ev.start:ev.end] == ev.quote


def test_rename_files_same_result(a):
    b = run(files(rename=True), CHECK)
    sig = lambda x: [(c.contract_no, [(f.value, f.state) for f in c.fields()]) for c in x.cards]
    assert sig(a) == sig(b)


def test_mutation_changes_output():
    def mut(name, text):
        return text.replace("840 000 (восемьсот сорок тысяч)", "910 000 (девятьсот десять тысяч)")
    c = card(run(files(mut), CHECK), "STN-102")
    assert c.amount.value == 910_000


def test_check_date_before_amendment():
    c = card(run(files(), date(2026, 2, 25)), "STN-101")
    assert c.term.value == date(2026, 4, 15) and c.term.state == State.OK
    assert any(p.kind == ProposalKind.SIGNED_NOT_YET_EFFECTIVE for p in c.proposals)


def test_new_contract_same_format():
    new = contract(no="STN-104", supplier="ООО «Новый Поставщик»", amount="455 000 (четыреста пятьдесят пять тысяч)",
                   term="25.03.2026")
    a = run(files() + [("new.txt", new.encode("utf-8"))], CHECK)
    c = card(a, "STN-104")
    assert (c.supplier.value, c.amount.value, c.term.value) == ("ООО «Новый Поставщик»", 455_000, date(2026, 3, 25))
    assert [r.card.contract_no for r in deadline_before(a, date(2026, 4, 1)).rows] == ["STN-102", "STN-104"]
