"""FastAPI application entrypoint for AccountantIQ."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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
