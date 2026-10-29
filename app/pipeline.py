"""Сквозной конвейер: файлы -> Analysis."""
from __future__ import annotations

from datetime import date

from .classify import classify
from .ingest import make_document
from .models import Document
from .resolve import Analysis, analyze


def load(files: list[tuple[str, bytes]]) -> list[Document]:
    return [classify(make_document(name, raw)) for name, raw in files]


def run(files: list[tuple[str, bytes]], check: date) -> Analysis:
    return analyze(load(files), check)
