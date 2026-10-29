from datetime import date

from app.models import State
from tests.helpers import analyze_texts, card, contract


def test_amount_and_term_basic():
    c = card(analyze_texts({"a.txt": contract()}), "ABC-7")
    assert c.amount.value == 2_500_000 and c.amount.state == State.OK
    assert c.term.value == date(2026, 3, 12) and c.term.state == State.OK
    assert "2 500 000" in c.amount.evidence[0].quote


def test_advance_payment_excluded():
    t = contract(extra_amount="2.2. Авансовый платеж составляет 500 000 рублей и входит в общую стоимость по пункту 2.1.")
    c = card(analyze_texts({"a.txt": t}), "ABC-7")
    assert c.amount.value == 2_500_000


def test_budget_limit_is_not_amount():
    clause = ("2.1. Общая стоимость определяется спецификацией в приложении № 2. "
              "Числовое значение стоимости в тексте договора не указано.")
    t = contract(amount_clause=clause,
                 extra_amount="2.2. Лимит закупки по внутреннему бюджету — 900 000 рублей. Этот лимит не является стоимостью договора.")
    c = card(analyze_texts({"a.txt": t}), "ABC-7")
    assert c.amount.state == State.NO_DATA and c.amount.value is None
    assert "приложении" in c.amount.evidence[0].quote   # основание отсутствия


def test_missing_amount_clause_is_no_data_without_evidence():
    t = contract(amount_clause="2.1. Порядок расчетов определяется отдельно.")
    c = card(analyze_texts({"a.txt": t}), "ABC-7")
    assert c.amount.state == State.NO_DATA and c.amount.value is None


def test_conflicting_amounts_need_review():
    t = contract(extra_amount="2.2. Общая стоимость поставки составляет 2 700 000 рублей.")
    c = card(analyze_texts({"a.txt": t}), "ABC-7")
    assert c.amount.state == State.NEEDS_REVIEW and c.amount.value is None


def test_payment_and_acceptance_dates_excluded():
    t = contract(extra_term="3.2. Оплата производится не позднее 20.04.2026. Дата приемки может отличаться от даты поставки и не изменяет срок по пункту 3.1.")
    c = card(analyze_texts({"a.txt": t}), "ABC-7")
    assert c.term.value == date(2026, 3, 12) and c.term.state == State.OK


def test_conflicting_terms_need_review():
    t = contract(extra_term="3.2. Поставщик обязуется поставить остаток товара не позднее 30.06.2026.")
    c = card(analyze_texts({"a.txt": t}), "ABC-7")
    assert c.term.state == State.NEEDS_REVIEW


def test_nbsp_and_plain_number_money():
    t = contract(amount="1\u00a0050\u00a0000")
    assert card(analyze_texts({"a.txt": t}), "ABC-7").amount.value == 1_050_000
    t = contract(amount="75000")
    assert card(analyze_texts({"a.txt": t}), "ABC-7").amount.value == 75_000


def test_price_of_contract_wording():
    t = contract(amount_clause="2.1. Цена договора составляет 330 000 (триста тридцать тысяч) рублей, включая НДС.")
    assert card(analyze_texts({"a.txt": t}), "ABC-7").amount.value == 330_000


def test_penalty_percent_is_not_amount():
    t = contract(extra_term="4.1. Неустойка составляет 0,1% стоимости договора за каждый день просрочки.")
    c = card(analyze_texts({"a.txt": t}), "ABC-7")
    assert c.amount.value == 2_500_000 and c.amount.state == State.OK
