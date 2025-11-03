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

The React shell calls the engine at `http://127.0.0.1:8000/health` and shows the current status.

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

## Sample data

You will find fake CSVs under `examples/` to help you validate parsers and matching heuristics as they are implemented.

## Contributing

- Trunk-based development with short-lived feature branches
- Keep stages scoped; ship README updates (with GIFs) before merging
- Run `pre-commit run --all-files` before pushing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.
