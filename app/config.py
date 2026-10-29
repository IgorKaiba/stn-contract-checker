"""Параметры приложения. Дата проверки — параметр, а не ответ."""
import os
from datetime import date, datetime

DEFAULT_CHECK_DATE = os.environ.get("STN_CHECK_DATE", "2026-03-10")


def parse_iso(value: str | None, fallback: str = DEFAULT_CHECK_DATE) -> date:
    try:
        return datetime.strptime((value or fallback).strip(), "%Y-%m-%d").date()
    except ValueError:
        return datetime.strptime(fallback, "%Y-%m-%d").date()

# Пресет вопроса 4 («поставка раньше даты X»): параметр формы, не результат.
DEFAULT_DEADLINE = os.environ.get("STN_DEADLINE_BEFORE", "2026-04-01")

# Необязательный LLM-слой (локальная Ollama). По умолчанию выключен: основной сценарий работает без модели.
LLM_MODE = os.environ.get("STN_LLM", "off")            # off | ollama
OLLAMA_URL = os.environ.get("STN_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("STN_OLLAMA_MODEL", "qwen2.5:7b-instruct")
