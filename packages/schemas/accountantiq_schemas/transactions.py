"""Typed schemas used across AccountantIQ services."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
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


class ReviewStatus(str, Enum):
    """Lifecycle state for a review item."""

    PENDING = "pending"
    APPROVED = "approved"
    OVERRIDDEN = "overridden"


class ReviewItem(FrozenModel):
    """A queue entry for human review."""

    txn: BankTxn
    suggestion: Suggestion
    status: ReviewStatus = ReviewStatus.PENDING
    nominal_final: Optional[str] = None
    tax_code_final: Optional[str] = None
    notes: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ReviewQueueResponse(FrozenModel):
    """Collection response for review queue listing."""

    items: list[ReviewItem]


class ReviewImportRequest(FrozenModel):
    """Import request to seed the review queue."""

    client_slug: str
    bank_csv: str
    history_csv: str
    reset: bool = True


class ApprovalRequest(FrozenModel):
    """Body for approving a queue item."""

    note: Optional[str] = None


class OverrideRequest(FrozenModel):
    """Body for overriding a queue item."""

    nominal_code: str
    tax_code: str
    note: Optional[str] = None


class RuleDefinition(FrozenModel):
    """Saved rule definition stored on disk."""

    name: str
    pattern: str
    nominal: str
    tax_code: str


class RuleCreateRequest(FrozenModel):
    """Request payload for creating a new rule."""

    name: str
    pattern: str
    nominal: str
    tax_code: str


class ProfileColumn(FrozenModel):
    """Column definition used by export profiles."""

    field: str
    header: str


class ProfileDefinition(FrozenModel):
    """Audit export profile definition."""

    name: str = "default"
    columns: list[ProfileColumn]


class ProfileSaveRequest(FrozenModel):
    """Payload for saving a profile definition."""

    profile: ProfileDefinition


class ExportRequest(FrozenModel):
    """Request body for generating an export file."""

    profile_name: str = "default"


class ExportResponse(FrozenModel):
    """Response shape when an export is created."""

    exported_path: str
    row_count: int


__all__ = [
    "ApprovalRequest",
    "BankTxn",
    "CsvSuggestionRequest",
    "CsvSuggestionResponse",
    "Direction",
    "ExportRequest",
    "ExportResponse",
    "OverrideRequest",
    "ProfileColumn",
    "ProfileDefinition",
    "ProfileSaveRequest",
    "ReviewImportRequest",
    "ReviewItem",
    "ReviewQueueResponse",
    "ReviewStatus",
    "RuleCreateRequest",
    "RuleDefinition",
    "SageHistoryEntry",
    "Suggestion",
    "SuggestionRequest",
    "SuggestionResponse",
]
