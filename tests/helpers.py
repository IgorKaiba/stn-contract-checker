"""Генератор синтетических документов того же общего формата (другие номера, суммы, даты)."""
from __future__ import annotations

from datetime import date

from app.pipeline import run

CHECK = date(2026, 3, 10)


def contract(no="ABC-7", supplier="ООО «Тест Поставка»", amount="2 500 000 (два миллиона пятьсот тысяч)",
             term="12.03.2026", extra_amount="", extra_term="", status="подписан обеими сторонами 01.02.2026.",
             amount_clause=None):
    amount_clause = amount_clause or (f"2.1. Общая стоимость поставки составляет {amount} рублей, включая НДС. "
                                      "Указанная сумма — итоговая стоимость договора.")
    return (f"ДОГОВОР ПОСТАВКИ № {no}\nДата: 01.02.2026\nСтатус: {status}\n\n"
            f"1.1. Покупатель: ООО «Покупатель Тест». Поставщик: {supplier}.\n1.2. Предмет: поставка товара.\n\n"
            f"{amount_clause}\n{extra_amount}\n\n"
            f"3.1. Поставщик обязуется поставить товар не позднее {term}.\n{extra_term}\n\n"
            "5.1. Изменения условий действуют после подписания дополнительного соглашения обеими сторонами.\n")


def amendment(no="ABC-7", supplier="ООО «Тест Поставка»", status="подписано обеими сторонами 01.03.2026.",
              effective="01.03.2026", new_amount="3 000 000", new_term="15.05.2026", title="ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ № 1"):
    eff = f"4. Настоящее соглашение вступает в силу {effective}.\n" if effective else ""
    return (f"{title} К ДОГОВОРУ {no}\nДата: 01.03.2026\nСтатус: {status}\n"
            f"Покупатель: ООО «Покупатель Тест». Поставщик: {supplier}.\n\n"
            f"1. Пункт 2.1 договора изложить в следующей редакции: «Общая стоимость поставки составляет {new_amount} рублей, включая НДС».\n\n"
            f"2. Пункт 3.1 договора изложить в следующей редакции: «Поставщик обязуется поставить товар не позднее {new_term}».\n\n"
            f"{eff}")


def letter(no="ABC-7", sender="ООО «Тест Поставка»", old="12.03.2026", new="19.03.2026"):
    return (f"ПИСЬМО ПОСТАВЩИКА\nДата: 05.03.2026\nОт: {sender}\nКому: ООО «Покупатель Тест»\nТема: договор {no}\n\n"
            f"Предлагаем перенести срок поставки с {old} на {new}. Просим подтвердить согласие.\n")


def analyze_texts(texts: dict[str, str], check=CHECK):
    return run([(n, t.encode("utf-8")) for n, t in texts.items()], check)


def card(a, no):
    return next(c for c in a.cards if c.contract_no == no)
