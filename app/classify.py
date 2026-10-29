"""A2 Classifier: тип документа, статус подписания, даты, стороны, номер договора.

Решения принимаются только по содержимому текста (заголовок, служебные строки),
имя файла и порядок загрузки не используются.
"""
from __future__ import annotations

import re

from .ingest import evidence
from .models import DocType, Document, Signed
from .textutil import DATE_RE, parse_date

CONTRACT_NO_RE = r"[A-ZА-ЯЁ]{2,}-\d+"
_NO_IN_HEADER = re.compile(r"№\s*(" + CONTRACT_NO_RE + r")")
_ANY_NO = re.compile(r"(?<![\w-])(" + CONTRACT_NO_RE + r")(?![\w-])")
_STATUS = re.compile(r"^\s*Статус\s*:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_DOC_DATE = re.compile(r"^\s*Дата(?:\s+проекта)?\s*:\s*(\d{2}\.\d{2}\.\d{4})", re.MULTILINE | re.IGNORECASE)
_EFFECTIVE = re.compile(r"вступает\s+в\s+силу\s+(?:с\s+)?(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE)
_TOPIC = re.compile(r"^\s*Тема\s*:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_FROM = re.compile(r"^\s*От\s*:\s*(.+?)\s*$", re.MULTILINE)
_TO = re.compile(r"^\s*Кому\s*:", re.MULTILINE)


def _party(role: str):
    # «Поставщик: ООО «Ромашка».» -> ООО «Ромашка»
    return re.compile(role + r"\s*:\s*(.+?)(?=\.\s|\.?\s*$)", re.MULTILINE)


_BUYER = _party("Покупатель")
_SUPPLIER = _party("Поставщик")

_POS_SIGNED = re.compile(r"подписан[оа]?\s+обеими\s+сторонами", re.IGNORECASE)
_NEG_SIGNED = re.compile(r"не\s+подписан|проект|на\s+согласовании|не\s+подписано", re.IGNORECASE)


def header_line(doc: Document) -> tuple[str, int, int]:
    for m in re.finditer(r"[^\n]+", doc.text):
        if m.group(0).strip():
            return m.group(0), m.start(), m.end()
    return "", 0, 0


def classify(doc: Document) -> Document:
    head, hs, he = header_line(doc)
    up = head.upper()
    status_m = _STATUS.search(doc.text)
    status = status_m.group(1) if status_m else ""
    ev = [evidence(doc, hs, he)]
    if status_m:
        ev.append(evidence(doc, status_m.start(1), status_m.end(1)))

    if "ПРОЕКТ" in up:
        dt = DocType.DRAFT
    elif "ДОПОЛНИТЕЛЬН" in up and "СОГЛАШЕН" in up:
        dt = DocType.AMENDMENT
    elif "ПИСЬМО" in up or (_FROM.search(doc.text) and _TO.search(doc.text)):
        dt = DocType.LETTER
    elif "ДОГОВОР" in up:
        dt = DocType.CONTRACT
    else:
        dt = DocType.UNKNOWN
    # Допсоглашение со статусом «проект» — это проект, независимо от заголовка.
    if dt == DocType.AMENDMENT and re.search(r"проект", status, re.IGNORECASE):
        dt = DocType.DRAFT
    doc.doc_type = dt

    pos, neg = bool(_POS_SIGNED.search(status)), bool(_NEG_SIGNED.search(status))
    if pos and not neg:
        doc.signed = Signed.SIGNED_BOTH
        d = DATE_RE.search(status)
        doc.sign_date = parse_date(d.group(0)) if d else None
    elif neg and not pos:
        doc.signed = Signed.NOT_SIGNED
    else:
        doc.signed = Signed.UNKNOWN

    m = _DOC_DATE.search(doc.text)
    doc.doc_date = parse_date(m.group(1)) if m else None
    m = _EFFECTIVE.search(doc.text)
    doc.effective_date = parse_date(m.group(1)) if m else None
    if m:
        ev.append(evidence(doc, m.start(), m.end()))

    m = _BUYER.search(doc.text)
    doc.buyer = m.group(1).strip() if m else None
    m = _SUPPLIER.search(doc.text)
    doc.supplier = m.group(1).strip() if m else None
    m = _FROM.search(doc.text)
    doc.sender = m.group(1).strip() if m else None

    doc.contract_no, doc.contract_no_note = _contract_no(doc, head)
    doc.classification_evidence = ev
    return doc


def _contract_no(doc: Document, head: str) -> tuple[str | None, str | None]:
    if doc.doc_type == DocType.CONTRACT:
        m = _NO_IN_HEADER.search(head) or _ANY_NO.search(head)
        return (m.group(1), None) if m else (None, "номер договора в заголовке не найден")
    m = _ANY_NO.search(head)
    if m:
        return m.group(1), None
    t = _TOPIC.search(doc.text)
    if t:
        m = _ANY_NO.search(t.group(1))
        if m:
            return m.group(1), None
    found = sorted(set(_ANY_NO.findall(doc.text)))
    if len(found) == 1:
        return found[0], None
    if not found:
        return None, "ссылка на договор не найдена"
    return None, "упомянуто несколько договоров: " + ", ".join(found)
