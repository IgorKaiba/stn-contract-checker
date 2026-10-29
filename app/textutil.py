"""Разбор текста на пункты и предложения с сохранением смещений."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
# 3 100 000 (прописью) рублей | 75000 руб. | 2 050 000 ₽
MONEY_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:,\d{1,2})?\s*(?:\([^)]*\)\s*)?(?:руб|₽)",
                      re.IGNORECASE)
_CLAUSE_NO = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[«\"(]?[А-ЯЁA-Z])")
SERVICE_LINE = re.compile(r"^\s*(Дата(?:\s+проекта)?|Статус|От|Кому|Тема)\s*:", re.IGNORECASE)


@dataclass
class Span:
    start: int
    end: int
    text: str


def parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%d.%m.%Y").date()
    except ValueError:
        return None


def dates_in(text: str) -> list[date]:
    out = []
    for m in DATE_RE.finditer(text):
        d = parse_date(m.group(0))
        if d:
            out.append(d)
    return out


def money_in(text: str) -> list[int]:
    return [int(re.sub(r"\D", "", m.group(1))) for m in MONEY_RE.finditer(text)]


def lines(text: str, start: int = 0, end: int | None = None) -> list[Span]:
    """Строки-пункты в диапазоне, без номера пункта в начале."""
    end = len(text) if end is None else end
    out = []
    pos = start
    for raw in text[start:end].split("\n"):
        s, e = pos, pos + len(raw)
        pos = e + 1
        m = _CLAUSE_NO.match(raw)
        if m:
            s += m.end()
        seg = text[s:e]
        if not seg.strip():
            continue
        lead = len(seg) - len(seg.lstrip())
        trail = len(seg) - len(seg.rstrip())
        out.append(Span(s + lead, e - trail, text[s + lead:e - trail]))
    return out


def sentences(text: str, span: Span) -> list[Span]:
    out = []
    pos = span.start
    for part in _SENT_SPLIT.split(span.text):
        idx = text.find(part, pos, span.end)
        if idx < 0:
            continue
        out.append(Span(idx, idx + len(part), part))
        pos = idx + len(part)
    return out


def fmt_money(v: int) -> str:
    return f"{v:,}".replace(",", "\u00a0") + "\u00a0₽"


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")
