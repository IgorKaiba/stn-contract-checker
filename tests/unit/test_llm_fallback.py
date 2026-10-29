import json

from app import llm_fallback
from app.classify import classify
from app.ingest import make_document
from app.models import State
from tests.helpers import analyze_texts, card, contract

ODD = contract(amount_clause="2.1. Цена всех товаров равна 640 000 рублей с НДС.")


def doc():
    return classify(make_document("x.txt", ODD.encode()))


def test_off_by_default_gives_no_data():
    assert card(analyze_texts({"x.txt": ODD}), "ABC-7").amount.state == State.NO_DATA


def test_exact_quote_accepted_as_needs_review():
    c = llm_fallback.suggest(doc(), "amount", client=lambda p: json.dumps({"quote": "Цена всех товаров равна 640 000 рублей с НДС."}))
    assert c.value == 640_000 and c.evidence.quote in ODD


def test_invented_quote_rejected():
    c = llm_fallback.suggest(doc(), "amount", client=lambda p: json.dumps({"quote": "Цена договора 999 000 рублей."}))
    assert c is None


def test_garbage_response_rejected():
    assert llm_fallback.suggest(doc(), "amount", client=lambda p: "not json") is None


def test_pipeline_marks_llm_value_for_review(monkeypatch):
    monkeypatch.setattr(llm_fallback.config, "LLM_MODE", "ollama")
    monkeypatch.setattr(llm_fallback, "_ollama", lambda p: json.dumps({"quote": "Цена всех товаров равна 640 000 рублей с НДС."}))
    c = card(analyze_texts({"x.txt": ODD}), "ABC-7")
    assert c.amount.state == State.NEEDS_REVIEW and c.amount.value == 640_000
