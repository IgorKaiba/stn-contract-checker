"""A3 Linker: договор -> связанные документы; непривязанные и предупреждения."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import DocType, Document


@dataclass
class Links:
    contracts: dict[str, Document] = field(default_factory=dict)
    related: dict[str, list[Document]] = field(default_factory=dict)
    duplicates: dict[str, list[Document]] = field(default_factory=dict)
    orphans: list[tuple[Document, str]] = field(default_factory=list)
    unknown: list[Document] = field(default_factory=list)
    warnings: dict[str, list[str]] = field(default_factory=dict)


def _norm(name: str | None) -> str:
    return " ".join((name or "").replace("\u00a0", " ").split()).lower()


def link(docs: list[Document]) -> Links:
    res = Links()
    for d in docs:
        if d.doc_type == DocType.CONTRACT:
            if not d.contract_no:
                res.orphans.append((d, d.contract_no_note or "номер договора не найден"))
            elif d.contract_no in res.contracts:
                res.duplicates.setdefault(d.contract_no, [res.contracts[d.contract_no]]).append(d)
            else:
                res.contracts[d.contract_no] = d
        elif d.doc_type == DocType.UNKNOWN:
            res.unknown.append(d)
    for d in docs:
        if d.doc_type in (DocType.CONTRACT, DocType.UNKNOWN):
            continue
        if not d.contract_no or d.contract_no not in res.contracts:
            res.orphans.append((d, d.contract_no_note or f"договор {d.contract_no} не загружен"))
            continue
        res.related.setdefault(d.contract_no, []).append(d)
        c = res.contracts[d.contract_no]
        w = res.warnings.setdefault(d.contract_no, [])
        if d.supplier and c.supplier and _norm(d.supplier) != _norm(c.supplier):
            w.append(f"{d.file_name}: поставщик «{d.supplier}» не совпадает с договором «{c.supplier}»")
        if d.doc_type == DocType.LETTER and d.sender and _norm(d.sender) not in {_norm(c.supplier), _norm(c.buyer)}:
            w.append(f"{d.file_name}: отправитель письма не является стороной договора")
    return res


def party_mismatch(doc: Document, contract: Document) -> bool:
    return bool(doc.supplier and contract.supplier and _norm(doc.supplier) != _norm(contract.supplier))
