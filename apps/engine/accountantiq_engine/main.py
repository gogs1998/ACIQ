"""FastAPI application entrypoint for AccountantIQ."""

from __future__ import annotations

from io import StringIO

from accountantiq_core import (
    BankCsvParser,
    ReviewStore,
    SageHistoryParser,
    append_rule,
    approved_items,
    export_review,
    list_profiles,
    load_profile,
    load_rules,
    match_rule,
    save_profile,
    suggest_for_transactions,
)
from accountantiq_schemas import (
    ApprovalRequest,
    BankTxn,
    CsvSuggestionRequest,
    CsvSuggestionResponse,
    ExportRequest,
    ExportResponse,
    OverrideRequest,
    ProfileDefinition,
    ProfileSaveRequest,
    ReviewImportRequest,
    ReviewItem,
    ReviewQueueResponse,
    RuleCreateRequest,
    RuleDefinition,
    Suggestion,
    SuggestionRequest,
    SuggestionResponse,
)
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

router = APIRouter(tags=["engine"])


def _apply_rules(
    client_slug: str,
    txns: list[BankTxn],
    suggestions: list[Suggestion],
) -> list[Suggestion]:
    rules = load_rules(client_slug)
    if not rules:
        return suggestions
    updated: list[Suggestion] = []
    for txn, suggestion in zip(txns, suggestions, strict=True):
        rule = match_rule(rules, txn)
        if rule is None:
            updated.append(suggestion)
            continue
        explanations = [
            f"Rule '{rule.name}' applied (pattern: {rule.pattern})",
            *suggestion.explanations,
        ]
        updated.append(
            suggestion.model_copy(
                update={
                    "nominal_suggested": rule.nominal,
                    "tax_code_suggested": rule.tax_code,
                    "confidence": max(suggestion.confidence, 0.95),
                    "explanations": explanations,
                }
            )
        )
    return updated


@router.post("/suggest", response_model=SuggestionResponse)
def suggest_codes(payload: SuggestionRequest) -> SuggestionResponse:
    """Return nominal/tax suggestions for the provided transactions."""
    suggestions = suggest_for_transactions(payload.transactions, payload.history)
    return SuggestionResponse(suggestions=suggestions)


@router.post("/suggest/from-csv", response_model=CsvSuggestionResponse)
def suggest_from_csv(payload: CsvSuggestionRequest) -> CsvSuggestionResponse:
    """Parse CSV content and return suggestions with the normalised rows."""
    bank_parser = BankCsvParser()
    history_parser = SageHistoryParser()
    bank_rows = bank_parser.parse(StringIO(payload.bank_csv))
    history_rows = history_parser.parse(StringIO(payload.history_csv))
    suggestions = suggest_for_transactions(bank_rows, history_rows)
    return CsvSuggestionResponse(transactions=bank_rows, suggestions=suggestions)


@router.post("/review/import", response_model=ReviewQueueResponse)
def import_review_queue(payload: ReviewImportRequest) -> ReviewQueueResponse:
    bank_parser = BankCsvParser()
    history_parser = SageHistoryParser()
    bank_rows = bank_parser.parse(StringIO(payload.bank_csv))
    history_rows = history_parser.parse(StringIO(payload.history_csv))
    suggestions = suggest_for_transactions(bank_rows, history_rows)
    suggestions = _apply_rules(payload.client_slug, bank_rows, suggestions)
    store = ReviewStore(payload.client_slug)
    items = store.import_batch(bank_rows, suggestions, reset=payload.reset)
    return ReviewQueueResponse(items=items)


@router.get("/review/{client_slug}/queue", response_model=ReviewQueueResponse)
def list_review_queue(client_slug: str) -> ReviewQueueResponse:
    store = ReviewStore(client_slug)
    return ReviewQueueResponse(items=store.list_items())


@router.post("/review/{client_slug}/items/{txn_id}/approve", response_model=ReviewItem)
def approve_item(
    client_slug: str,
    txn_id: str,
    payload: ApprovalRequest | None = None,
) -> ReviewItem:
    store = ReviewStore(client_slug)
    try:
        return store.approve(txn_id, payload)
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/review/{client_slug}/items/{txn_id}/override", response_model=ReviewItem)
def override_item(
    client_slug: str,
    txn_id: str,
    payload: OverrideRequest,
) -> ReviewItem:
    store = ReviewStore(client_slug)
    try:
        return store.override(txn_id, payload)
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/review/{client_slug}/rules", response_model=list[RuleDefinition])
def list_rules(client_slug: str) -> list[RuleDefinition]:
    return load_rules(client_slug)


@router.post("/review/{client_slug}/rules", response_model=list[RuleDefinition])
def create_rule(client_slug: str, payload: RuleCreateRequest) -> list[RuleDefinition]:
    rule = RuleDefinition(**payload.model_dump())
    return append_rule(client_slug, rule)


@router.get("/review/{client_slug}/profiles", response_model=list[ProfileDefinition])
def get_profiles(client_slug: str) -> list[ProfileDefinition]:
    return list_profiles(client_slug)


@router.post("/review/{client_slug}/profile", response_model=ProfileDefinition)
def save_profile_definition(
    client_slug: str,
    payload: ProfileSaveRequest,
) -> ProfileDefinition:
    save_profile(client_slug, payload.profile)
    return payload.profile


@router.post("/review/{client_slug}/export", response_model=ExportResponse)
def export_review_items(
    client_slug: str,
    payload: ExportRequest | None = None,
) -> ExportResponse:
    store = ReviewStore(client_slug)
    items = approved_items(store.list_items())
    if not items:
        raise HTTPException(status_code=400, detail="No approved items to export")
    profile_name = payload.profile_name if payload else "default"
    profile = load_profile(client_slug, profile_name)
    path = export_review(client_slug, items, profile)
    return ExportResponse(exported_path=path, row_count=len(items))


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(title="AccountantIQ Engine", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])  # pragma: no cover - trivial
    def healthcheck() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(router)

    return app


app = create_app()


def run() -> None:  # pragma: no cover - manual entrypoint
    """Run the development server with uvicorn."""
    import uvicorn

    uvicorn.run(
        "accountantiq_engine.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    run()
