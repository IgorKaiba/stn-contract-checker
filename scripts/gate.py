"""Anti-hardcode gate: код приложения (app/) не должен содержать данных учебного комплекта.

Запуск: python scripts/gate.py   (код 0 и "GATE: PASS" = нарушений нет)
Это сигнализация, а не доказательство: основная защита — тесты на синтетических документах.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    r"STN-\d", r"Вектор", r"Контур", r"ПромСнаб", r"СеверМет",
    r"1 ?380 ?000", r"840 ?000", r"1 ?200 ?000", r"1 ?450 ?000", r"600 ?000",
    r"\d{2}_contract", r"\d{2}_amendment", r"supplier_email",
    r"file_name\s*==",
]
# Даты в коде допустимы только в config.py (параметры по умолчанию).
DATE = r"\b\d{2}\.\d{2}\.\d{4}\b|\b\d{4}-\d{2}-\d{2}\b"
DATE_ALLOWED = {"config.py"}


def scan() -> list[str]:
    hits = []
    rx = re.compile("|".join(PATTERNS), re.IGNORECASE)
    rd = re.compile(DATE)
    for path in sorted((ROOT / "app").rglob("*")):
        if path.suffix not in {".py", ".html"}:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if rx.search(line) or (path.name not in DATE_ALLOWED and rd.search(line)):
                hits.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    return hits


if __name__ == "__main__":
    found = scan()
    print("\n".join(found))
    print("GATE: FAIL" if found else "GATE: PASS")
    sys.exit(1 if found else 0)
