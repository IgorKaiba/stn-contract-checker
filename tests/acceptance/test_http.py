"""HTTP-сценарий закупщика через TestClient."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main

DOCS = Path(__file__).resolve().parents[2] / "documents"


@pytest.fixture()
def client():
    main.STORE.clear()
    c = TestClient(main.app)
    files = [("files", (p.name, p.read_bytes(), "text/plain")) for p in sorted(DOCS.glob("*.txt"))]
    r = c.post("/upload", files=files, data={"check_date": "2026-03-10"})
    assert r.status_code == 200          # после редиректа
    yield c
    main.STORE.clear()


def test_table_page(client):
    html = client.get("/").text
    for no in ("STN-101", "STN-102", "STN-103"):
        assert no in html
    assert "нет данных" in html and "изменено ДС" in html and "проект, не подписан" in html


def test_api_and_evidence_links(client):
    data = client.get("/api/table").json()
    assert len(data["contracts"]) == 3
    links = 0
    for c in data["contracts"]:
        for f in ("amount", "term"):
            for ev in c[f]["evidence"]:
                page = client.get(ev["link"].split("#")[0])
                assert page.status_code == 200
                assert f'id="{ev["paragraph"]}"' in page.text
                assert "<mark>" in page.text
                links += 1
    assert links >= 6


def test_questions_pages(client):
    r = client.get("/ask", params={"q": "term", "no": "STN-101", "on": "2026-03-10"}).text
    assert "30.04.2026" in r and "02_amendment_signed.txt" in r
    r = client.get("/ask", params={"q": "amount", "no": "STN-102"}).text
    assert "840" in r
    r = client.get("/ask", params={"q": "amount", "no": "STN-103"}).text
    assert "нет данных" in r
    r = client.get("/ask", params={"q": "deadline", "before": "2026-04-01"}).text
    block = r.split("Ответ", 1)[1]
    assert "STN-102" in block and "STN-101" not in re.sub(r"<[^>]+>", "", block).split("Срок не определён")[0] \
        and "Есть несогласованное изменение срока" in block


def test_reupload_same_name_replaces(client):
    p = DOCS / "03_contract.txt"
    text = p.read_text(encoding="utf-8").replace("840 000 (восемьсот сорок тысяч)", "910 000 (девятьсот десять тысяч)")
    client.post("/upload", files=[("files", (p.name, text.encode(), "text/plain"))])
    c = next(x for x in client.get("/api/table").json()["contracts"] if x["contract_no"] == "STN-102")
    assert "910" in c["amount"]["display"]


def test_cp1251_upload(client):
    text = (DOCS / "04_contract.txt").read_text(encoding="utf-8").replace("STN-103", "STN-109")
    client.post("/upload", files=[("files", ("cp.txt", text.encode("cp1251"), "text/plain"))])
    nos = [x["contract_no"] for x in client.get("/api/table").json()["contracts"]]
    assert "STN-109" in nos
