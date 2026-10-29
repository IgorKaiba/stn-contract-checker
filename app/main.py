"""Веб-интерфейс прототипа (FastAPI + Jinja2). Хранилище — в памяти, один локальный пользователь."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from .config import DEFAULT_CHECK_DATE, DEFAULT_DEADLINE, parse_iso
from .extract import LABELS
from .models import DocType, Document, FieldValue, ProposalKind, Signed, State
from .pipeline import load
from .queries import deadline_before, field_on
from .resolve import analyze
from .textutil import fmt_date, fmt_money

app = FastAPI(title="Проверка условий договоров поставки")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
STORE: dict[str, Document] = {}          # file_name -> Document (повторная загрузка заменяет)
STATE = {"check_date": parse_iso(DEFAULT_CHECK_DATE)}

STATE_LABEL = {State.OK: "по договору", State.CHANGED: "изменено ДС", State.NO_DATA: "нет данных",
               State.NEEDS_REVIEW: "требует проверки"}
KIND_LABEL = {ProposalKind.DRAFT: "проект, не подписан", ProposalKind.LETTER: "письмо (предложение)",
              ProposalKind.SIGNED_NOT_YET_EFFECTIVE: "ДС подписано, ещё не вступило в силу"}
TYPE_LABEL = {DocType.CONTRACT: "договор", DocType.AMENDMENT: "допсоглашение", DocType.DRAFT: "проект изменения",
              DocType.LETTER: "письмо", DocType.UNKNOWN: "не распознан"}
SIGNED_LABEL = {Signed.SIGNED_BOTH: "подписан обеими сторонами", Signed.NOT_SIGNED: "не подписан",
                Signed.UNKNOWN: "не определён"}


def fmt_value(field: str, v) -> str:
    if v is None:
        return "нет данных"
    if isinstance(v, date):
        return fmt_date(v)
    if field == "amount":
        return fmt_money(v)
    return str(v)


def show(fv: FieldValue) -> str:
    if fv.state == State.NO_DATA:
        return "нет данных"
    if fv.state == State.NEEDS_REVIEW and fv.value is None:
        return "требует проверки"
    return fmt_value(fv.field, fv.value)


templates.env.globals.update(fmt_value=fmt_value, show=show, STATE_LABEL=STATE_LABEL, KIND_LABEL=KIND_LABEL,
                             TYPE_LABEL=TYPE_LABEL, SIGNED_LABEL=SIGNED_LABEL, LABELS=LABELS, fmt_date=fmt_date,
                             State=State, DEFAULT_DEADLINE=DEFAULT_DEADLINE, parse_d=parse_iso)


def _check(value: str | None) -> date:
    if value:
        STATE["check_date"] = parse_iso(value, STATE["check_date"].isoformat())
    return STATE["check_date"]


def _analysis(check: date):
    return analyze(list(STORE.values()), check)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, check_date: str | None = None):
    check = _check(check_date)
    a = _analysis(check)
    return templates.TemplateResponse(request, "index.html", {"a": a, "check": check, "store": STORE})


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...), check_date: str = Form(None)):
    _check(check_date)
    pairs = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".txt"):
            continue
        pairs.append((Path(f.filename).name, await f.read()))
    for doc in load(pairs):
        STORE[doc.file_name] = doc
    return RedirectResponse("/", status_code=303)


@app.post("/reset")
def reset():
    STORE.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/doc/{doc_id}", response_class=HTMLResponse)
def doc_view(request: Request, doc_id: str, s: int | None = None, e: int | None = None):
    doc = next((d for d in STORE.values() if d.doc_id == doc_id), None)
    if not doc:
        return HTMLResponse("Документ не найден (загрузите файлы заново)", status_code=404)
    paras = []
    for p in doc.paragraphs:
        if s is not None and e is not None and p.start <= s < p.end:
            a, b = s - p.start, min(e, p.end) - p.start
            html = escape(p.text[:a]) + Markup("<mark>") + escape(p.text[a:b]) + Markup("</mark>") + escape(p.text[b:])
        else:
            html = escape(p.text)
        paras.append((p, html))
    return templates.TemplateResponse(request, "doc.html", {"doc": doc, "paras": paras})


@app.get("/ask", response_class=HTMLResponse)
def ask(request: Request, q: str | None = None, no: str | None = None, on: str | None = None,
        before: str | None = None):
    check = STATE["check_date"]
    a = _analysis(check)
    answer = None
    if q in ("term", "amount") and no:
        answer = ("field", field_on(a, no, q, parse_iso(on, check.isoformat()) if on else check))
    elif q == "deadline":
        answer = ("deadline", deadline_before(a, parse_iso(before, DEFAULT_DEADLINE)))
    return templates.TemplateResponse(request, "ask.html", {"a": a, "check": check, "answer": answer, "q": q,
                                                            "no": no, "on": on, "before": before or DEFAULT_DEADLINE})


def _ev(ev):
    return {"file": ev.file_name, "paragraph": ev.pid, "quote": ev.quote, "link": f"/doc/{ev.doc_id}?s={ev.start}&e={ev.end}#{ev.pid}"}


def _fv(fv: FieldValue, a):
    return {"value": fmt_value(fv.field, fv.value) if fv.value is not None else None, "display": show(fv),
            "state": fv.state.value, "reason": fv.reason, "evidence": [_ev(x) for x in fv.evidence],
            "changed_by": a.docs[fv.changed_by].file_name if fv.changed_by else None,
            "base_value": fmt_value(fv.field, fv.base_value) if fv.state == State.CHANGED else None,
            "base_evidence": [_ev(x) for x in fv.base_evidence]}


@app.get("/api/table")
def api_table(check_date: str | None = None):
    check = parse_iso(check_date, STATE["check_date"].isoformat()) if check_date else STATE["check_date"]
    a = _analysis(check)
    return JSONResponse({
        "check_date": check.isoformat(),
        "contracts": [{"contract_no": c.contract_no, "supplier": _fv(c.supplier, a), "amount": _fv(c.amount, a),
                       "term": _fv(c.term, a), "warnings": c.warnings,
                       "pending": [{"field": p.field, "proposed": fmt_value(p.field, p.proposed_value),
                                    "kind": p.kind.value, "source": a.docs[p.source_doc_id].file_name,
                                    "evidence": [_ev(x) for x in p.evidence]} for p in c.proposals]}
                      for c in a.cards],
        "orphans": [{"file": d.file_name, "reason": r} for d, r in a.links.orphans],
        "unknown": [d.file_name for d in a.links.unknown],
    })
