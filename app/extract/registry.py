"""Реестр извлекателей: поле -> функция(doc, region) -> list[Candidate].

Новое поле (например, ставка неустойки) = одна функция + регистрация + тест.
region: (start, end) — диапазон текста документа; для допсоглашения это текст
новой редакции пункта в кавычках, для договора — тело документа.
"""
from __future__ import annotations

from typing import Callable

from ..models import Candidate, Document

Extractor = Callable[[Document, tuple[int, int]], list[Candidate]]
REGISTRY: dict[str, Extractor] = {}
LABELS: dict[str, str] = {}


def register(field: str, label: str):
    def deco(fn: Extractor) -> Extractor:
        REGISTRY[field] = fn
        LABELS[field] = label
        return fn
    return deco
