import random
from datetime import date

from app.classify import classify
from app.ingest import make_document
from app.models import DocType, ProposalKind, Signed, State
from tests.helpers import amendment, analyze_texts, card, contract, letter


def cls(text):
    return classify(make_document("x.txt", text.encode("utf-8")))


def test_doc_types_and_status():
    assert cls(contract()).doc_type == DocType.CONTRACT
    a = cls(amendment())
    assert a.doc_type == DocType.AMENDMENT and a.signed == Signed.SIGNED_BOTH and a.effective_date == date(2026, 3, 1)
    d = cls(amendment(title="ПРОЕКТ ДОПОЛНИТЕЛЬНОГО СОГЛАШЕНИЯ № 2", status="проект, не подписан ни одной стороной."))
    assert d.doc_type == DocType.DRAFT and d.signed == Signed.NOT_SIGNED
    assert cls(letter()).doc_type == DocType.LETTER
    assert cls("Просто заметка без структуры").doc_type == DocType.UNKNOWN


def test_ambiguous_status_is_unknown():
    assert cls(amendment(status="не подписано обеими сторонами.")).signed == Signed.UNKNOWN


def test_effective_amendment_changes_values():
    c = card(analyze_texts({"c.txt": contract(), "a.txt": amendment()}), "ABC-7")
    assert c.amount.state == State.CHANGED and c.amount.value == 3_000_000 and c.amount.base_value == 2_500_000
    assert c.term.state == State.CHANGED and c.term.value == date(2026, 5, 15)
    assert c.amount.evidence[0].file_name == "a.txt" and c.amount.base_evidence[0].file_name == "c.txt"


def test_future_effective_amendment_is_proposal():
    c = card(analyze_texts({"c.txt": contract(), "a.txt": amendment(effective="01.04.2026")}), "ABC-7")
    assert c.amount.state == State.OK and c.amount.value == 2_500_000
    assert {p.kind for p in c.proposals} == {ProposalKind.SIGNED_NOT_YET_EFFECTIVE}


def test_check_date_before_amendment_keeps_base():
    c = card(analyze_texts({"c.txt": contract(), "a.txt": amendment()}, check=date(2026, 2, 15)), "ABC-7")
    assert c.term.state == State.OK and c.term.value == date(2026, 3, 12)
    assert any(p.field == "term" for p in c.proposals)


def test_amendment_without_effective_date_needs_review():
    c = card(analyze_texts({"c.txt": contract(), "a.txt": amendment(effective=None)}), "ABC-7")
    assert c.amount.state == State.NEEDS_REVIEW and c.term.state == State.NEEDS_REVIEW


def test_amendment_unknown_status_needs_review():
    c = card(analyze_texts({"c.txt": contract(), "a.txt": amendment(status="на подписи")}), "ABC-7")
    assert c.term.state == State.NEEDS_REVIEW


def test_amendment_supplier_mismatch_needs_review():
    c = card(analyze_texts({"c.txt": contract(), "a.txt": amendment(supplier="ООО «Другая Фирма»")}), "ABC-7")
    assert c.amount.state == State.NEEDS_REVIEW and c.warnings


def test_draft_and_letter_do_not_change():
    texts = {"c.txt": contract(), "l.txt": letter(),
             "d.txt": amendment(title="ПРОЕКТ ДОПОЛНИТЕЛЬНОГО СОГЛАШЕНИЯ № 2", status="проект на согласовании.")}
    c = card(analyze_texts(texts), "ABC-7")
    assert c.term.state == State.OK and c.term.value == date(2026, 3, 12)
    kinds = {(p.field, p.kind) for p in c.proposals}
    assert ("term", ProposalKind.LETTER) in kinds and ("amount", ProposalKind.DRAFT) in kinds


def test_two_effective_amendments_latest_wins_and_tie_needs_review():
    a1 = amendment(new_term="15.05.2026")
    a2 = amendment(new_term="20.05.2026", effective="05.03.2026").replace("Дата: 01.03.2026", "Дата: 05.03.2026") \
        .replace("№ 1", "№ 3")
    c = card(analyze_texts({"c.txt": contract(), "a1.txt": a1, "a2.txt": a2}), "ABC-7")
    assert c.term.value == date(2026, 5, 20)
    a3 = amendment(new_term="25.05.2026")
    c = card(analyze_texts({"c.txt": contract(), "a1.txt": a1, "a3.txt": a3}), "ABC-7")
    assert c.term.state == State.NEEDS_REVIEW


def test_load_order_and_names_do_not_matter():
    texts = [contract(), amendment(), letter()]
    base = analyze_texts({f"{i}.txt": t for i, t in enumerate(texts)})
    random.seed(1)
    for _ in range(5):
        random.shuffle(texts)
        names = [f"{random.randint(1000, 9999)}_doc.txt" for _ in texts]
        other = analyze_texts(dict(zip(names, texts)))
        assert [(f.value, f.state) for f in other.cards[0].fields()] == [(f.value, f.state) for f in base.cards[0].fields()]


def test_orphan_and_duplicate():
    a = analyze_texts({"a.txt": amendment(no="ZZZ-1")})
    assert not a.cards and a.links.orphans
    a = analyze_texts({"c1.txt": contract(), "c2.txt": contract(amount="1 000 000")})
    assert all(f.state == State.NEEDS_REVIEW for f in a.cards[0].fields())


def test_nested_quotes_in_rewrite():
    am = amendment().replace("«Общая стоимость поставки составляет 3 000 000 рублей, включая НДС»",
                             "«Общая стоимость поставки по заказу «Север» составляет 3 000 000 рублей, включая НДС»")
    c = card(analyze_texts({"c.txt": contract(), "a.txt": am}), "ABC-7")
    assert c.amount.value == 3_000_000 and c.amount.state == State.CHANGED
