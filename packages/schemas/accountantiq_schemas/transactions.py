"""Typed schemas used across AccountantIQ services."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["debit", "credit"]


class FrozenModel(BaseModel):
    """Base model with shared configuration settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class BankTxn(FrozenModel):
    """Normalised view of a bank transaction."""

    id: str
    date: date
    amount: float
    direction: Direction
    description_raw: str
    description_clean: str
    account_id: str


class SageHistoryEntry(FrozenModel):
    """Snapshot of a historical posting exported from Sage."""

    id: str
    date: date
    amount: float
    nominal_code: str
    tax_code: str
    description_raw: str
    description_clean: str
    vendor_hint: Optional[str] = None


class Suggestion(FrozenModel):
    """Suggested nominal/tax codes for a transaction."""

    txn_id: str
    nominal_suggested: Optional[str] = None
    tax_code_suggested: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    explanations: list[str] = Field(default_factory=list)


class SuggestionRequest(FrozenModel):
    """Payload accepted by the `/suggest` endpoint."""

    transactions: list[BankTxn]
    history: list[SageHistoryEntry]


class SuggestionResponse(FrozenModel):
    """Response envelope returned by the `/suggest` endpoint."""

    suggestions: list[Suggestion]


class CsvSuggestionRequest(FrozenModel):
    """Request body for submitting raw CSV content."""

    bank_csv: str
    history_csv: str


class CsvSuggestionResponse(FrozenModel):
    """Response including both transactions and their suggestions."""

    transactions: list[BankTxn]
    suggestions: list[Suggestion]


__all__ = [
    "BankTxn",
    "Direction",
    "SageHistoryEntry",
    "Suggestion",
    "SuggestionRequest",
    "SuggestionResponse",
    "CsvSuggestionRequest",
    "CsvSuggestionResponse",
]
