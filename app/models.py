"""Модель данных конвейера (A1–A6)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class DocType(str, Enum):
    CONTRACT = "CONTRACT"
    AMENDMENT = "AMENDMENT"
    DRAFT = "DRAFT"
    LETTER = "LETTER"
    UNKNOWN = "UNKNOWN"


class Signed(str, Enum):
    SIGNED_BOTH = "SIGNED_BOTH"
    NOT_SIGNED = "NOT_SIGNED"
    UNKNOWN = "UNKNOWN"


class State(str, Enum):
    OK = "OK"
    CHANGED = "CHANGED"
    NO_DATA = "NO_DATA"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ProposalKind(str, Enum):
    DRAFT = "DRAFT"
    LETTER = "LETTER"
    SIGNED_NOT_YET_EFFECTIVE = "SIGNED_NOT_YET_EFFECTIVE"


@dataclass
class Paragraph:
    pid: str          # "p-<n>", нумерация с 1
    start: int
    end: int
    text: str


@dataclass
class Evidence:
    doc_id: str
    file_name: str
    pid: str
    quote: str        # == document.text[start:end]
    start: int
    end: int


@dataclass
class Document:
    doc_id: str
    file_name: str
    text: str
    paragraphs: list[Paragraph]
    encoding_note: str | None = None
    doc_type: DocType = DocType.UNKNOWN
    signed: Signed = Signed.UNKNOWN
    sign_date: date | None = None
    doc_date: date | None = None
    effective_date: date | None = None
    contract_no: str | None = None
    contract_no_note: str | None = None
    buyer: str | None = None
    supplier: str | None = None
    sender: str | None = None
    classification_evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Candidate:
    """Найденное извлекателем значение поля с основанием."""
    field: str
    value: object | None
    evidence: Evidence | None
    no_data: bool = False


@dataclass
class FieldValue:
    field: str
    value: object | None
    state: State
    evidence: list[Evidence] = field(default_factory=list)
    changed_by: str | None = None          # doc_id допсоглашения
    base_value: object | None = None
    base_evidence: list[Evidence] = field(default_factory=list)
    reason: str | None = None


@dataclass
class Proposal:
    contract_no: str
    field: str
    proposed_value: object
    source_doc_id: str
    kind: ProposalKind
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class ContractCard:
    contract_no: str
    contract_doc_id: str
    supplier: FieldValue
    amount: FieldValue
    term: FieldValue
    proposals: list[Proposal] = field(default_factory=list)
    related_docs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fields(self) -> list[FieldValue]:
        return [self.supplier, self.amount, self.term]
