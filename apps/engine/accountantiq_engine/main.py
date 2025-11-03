"""FastAPI application entrypoint for AccountantIQ."""

from __future__ import annotations

from io import StringIO

from accountantiq_core import BankCsvParser, SageHistoryParser, suggest_for_transactions
from accountantiq_schemas import (
    CsvSuggestionRequest,
    CsvSuggestionResponse,
    SuggestionRequest,
    SuggestionResponse,
)
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

router = APIRouter(tags=["suggestions"])


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

    @app.get("/health", tags=["system"])
    def healthcheck() -> dict[str, bool]:
        """Confirm the engine is running."""
        return {"ok": True}

    app.include_router(router)

    return app


app = create_app()


def run() -> None:
    """Run the development server with uvicorn."""
    import uvicorn

    uvicorn.run(
        "accountantiq_engine.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    run()
