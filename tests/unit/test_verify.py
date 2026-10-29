from app.models import State
from app.verify import verify_card
from tests.helpers import analyze_texts, contract


def test_tampered_quote_is_caught():
    a = analyze_texts({"c.txt": contract()})
    c = a.cards[0]
    c.amount.evidence[0].quote = c.amount.evidence[0].quote.replace("2 500 000", "2 600 000")
    verify_card(c, a.docs)
    assert c.amount.state == State.NEEDS_REVIEW and "V1" in c.amount.reason


def test_every_quote_is_exact_slice():
    a = analyze_texts({"c.txt": contract()})
    for fv in a.cards[0].fields():
        for ev in fv.evidence:
            d = a.docs[ev.doc_id]
            assert d.text[ev.start:ev.end] == ev.quote
            p = next(p for p in d.paragraphs if p.pid == ev.pid)
            assert ev.quote in p.text or p.text in ev.quote
