"""Необязательный fallback на локальную модель (Ollama), когда правила не нашли пункт.

Гейт V1: ответ модели принимается, только если цитата буквально присутствует в тексте
документа. Принятое значение всегда получает статус «требует проверки».
Без запущенной Ollama модуль ничего не делает (STN_LLM=off по умолчанию).
"""
from __future__ import annotations

import json
import urllib.request
from typing import Callable

from . import config
from .ingest import evidence
from .models import Candidate, Document
from .textutil import dates_in, money_in

PROMPTS = {
    "amount": "Найди в тексте договора итоговую стоимость договора в рублях (не аванс, не лимит бюджета).",
    "term": "Найди в тексте договора срок поставки (не срок оплаты и не дату приемки).",
}
SCHEMA = {"type": "object", "properties": {"quote": {"type": "string"}}, "required": ["quote"]}


def _ollama(prompt: str) -> str:
    body = json.dumps({"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": SCHEMA,
                       "options": {"temperature": 0, "seed": 7, "num_ctx": 8192}}).encode()
    req = urllib.request.Request(config.OLLAMA_URL + "/api/generate", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["response"]


def suggest(doc: Document, field: str, client: Callable[[str], str] | None = None) -> Candidate | None:
    if field not in PROMPTS or (client is None and config.LLM_MODE != "ollama"):
        return None
    prompt = (PROMPTS[field] + " Верни JSON {\"quote\": \"...\"} с ТОЧНОЙ дословной цитатой предложения из текста. "
              "Если сведений нет — {\"quote\": \"\"}.\n\nТЕКСТ:\n" + doc.text)
    try:
        quote = json.loads((client or _ollama)(prompt)).get("quote", "").strip()
    except Exception:
        return None
    idx = doc.text.find(quote) if quote else -1
    if idx < 0:                                     # V1: выдуманная или искажённая цитата отбрасывается
        return None
    value = (money_in(quote) or [None])[0] if field == "amount" else (dates_in(quote) or [None])[0]
    if value is None:
        return None
    return Candidate(field, value, evidence(doc, idx, idx + len(quote)))
