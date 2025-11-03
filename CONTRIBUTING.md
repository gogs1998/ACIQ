# Contributing

Thanks for helping build AccountantIQ! This project is organised into well-defined stages. Please keep your contributions scoped so we can ship value after each stage.

## Workflow

1. Create a feature branch off `main` using the convention `feat/<summary>` or `chore/<summary>`.
2. Run `poetry install` and `pnpm install` (inside `apps/ui`) once after cloning.
3. Use `poetry run uvicorn accountantiq_engine.main:app --reload` for local API development and `pnpm dev` for the desktop shell.
4. Ensure linters and tests pass before opening a pull request:
   - `poetry run ruff check apps packages`
   - `poetry run black --check apps packages`
   - `poetry run mypy apps/engine packages`
   - `poetry run pytest -q`
   - `pnpm --filter ui lint`
   - `pnpm --filter ui test`
5. Update the README with new commands, configuration, or screenshots or GIFs whenever behaviour changes.
6. Squash merge once approved.

## Commit message style

Follow [Conventional Commits](https://www.conventionalcommits.org/) to make the change history scannable, e.g. `feat(engine): add health endpoint`.

## Code style

- Python: keep functions typed and prefer pure utilities in `packages/`
- Frontend: TypeScript strict mode; colocate tests with the components they cover
- Keep configuration files ASCII where possible

## Project board

The GitHub project uses columns: Backlog > Next > In Progress > Review > Done. Move cards during stand-ups so the team always knows the live status.
