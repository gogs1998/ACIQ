# AccountantIQ

Local-first tooling that helps accountants normalise bank statements, learn from Sage 50 history, and propose the right nominal codes every time.

## Monorepo layout

```
accountantiq/
  apps/
    engine/          # FastAPI local engine
    ui/              # Tauri + React desktop client
  packages/
    core/            # Shared Python utilities (parsers, matchers, etc.)
    schemas/         # Pydantic models shared across services
    prompts/         # Prompt snippets and few-shot examples
  examples/          # Sample CSV inputs for development and tests
  data/              # Local workspaces (gitignored)
  .github/workflows/ # CI definitions
```

## Prerequisites

- Python 3.11
- [Poetry](https://python-poetry.org/) 1.7+
- Node.js 18+
- [pnpm](https://pnpm.io/) 8+
- Rust toolchain and Tauri prerequisites (Windows: Visual Studio Build Tools; macOS: Xcode Command Line Tools)

## Quick start

```bash
# 1. Install python deps
poetry install

# 2. Run the engine locally
poetry run uvicorn accountantiq_engine.main:app --reload

# 3. Install UI deps
cd apps/ui
pnpm install

# 4. Start the desktop shell (web preview)
pnpm dev
```

The React shell calls the engine at `http://127.0.0.1:8000` for health checks, suggestions, and the review workflow.

### Formatting and linting

```bash
poetry run ruff check apps packages
poetry run black --check apps packages
poetry run mypy apps/engine packages
pnpm --filter ui lint
```

### Tests

```bash
poetry run pytest -q
pnpm --filter ui test
```

### Building the desktop app

```bash
pnpm tauri build
```

See the [Tauri prerequisites guide](https://tauri.app/v1/guides/getting-started/prerequisites) for platform-specific tooling.

## Stage 2 workflow � review queue and export

1. Drop bank CSVs and audit trail exports under `data/clients/<slug>/inputs/{bank,sage_history}`.
2. Launch the engine and UI (commands above). In the UI, set the client slug, load CSVs, and run suggestions. Toggle “Auto-create rules during import” if you want high-confidence matches to be saved as regex rules automatically, or use the “Auto-create rules” button to backfill them later. The review queue displays confidence, allows manual overrides, and captures rules straight into `workspace/rules/rules.yaml`.
3. Approved/overridden rows can be exported with the "Export approved items" button. Files are written to `data/clients/<slug>/outputs/sage_import_*.csv` using the active export profile.
4. Use the engine API directly if needed:
   - `POST /review/import` � seed the queue from CSV payloads.
   - `POST /review/{slug}/items/{txn_id}/approve` � accept a suggestion.
   - `POST /review/{slug}/items/{txn_id}/override` � apply manual coding.
   - `POST /review/{slug}/rules` � append vendor rules.
   - `POST /review/{slug}/export` � generate an audit trail CSV via the current profile.

## Sample data

You will find fake CSVs under `examples/` to help you validate parsers and matching heuristics as they are implemented.

## Contributing

- Trunk-based development with short-lived feature branches
- Keep stages scoped; ship README updates (with GIFs) before merging
- Run `pre-commit run --all-files` before pushing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.
