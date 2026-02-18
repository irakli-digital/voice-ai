# Repository Guidelines

## Project Structure & Modules
- `agent/` — Python LiveKit agent: `agent.py` (entry), `wisprflow_stt.py` (Georgian STT), `db.py` (SQLite logging), `pyproject.toml` (deps).
- `web/` — Next.js app: `app/` (routes, API), `components/` (UI), `package.json`.
- `PRD.md` (product spec), `README.md` (setup), local env files in `agent/.env.local` and `web/.env.local`.

## Build, Test, and Development
- Agent (first time): `cd agent && uv sync`
- Agent (console mode): `uv run agent.py console`
- Agent (LiveKit dev): `uv run agent.py dev` (set `STT_PROVIDER=openai|wisprflow`)
- Web (first time): `cd web && npm install`
- Web (dev server): `npm run dev`
- Web (build/start): `npm run build && npm start`

## Coding Style & Naming
- Python: PEP 8, 4‑space indent, type hints required on public funcs. Files/modules `snake_case.py`; classes `PascalCase`; functions/vars `snake_case`. Keep side effects in `if __name__ == "__main__":` blocks.
- TypeScript/React: Prefer functional components and hooks. Components `PascalCase` in `web/components/` (e.g., `VoiceAgent.tsx`); route files in `web/app/` are lower‑case (e.g., `page.tsx`). Use named exports where possible.
- Keep functions small; isolate I/O (LiveKit, STT, TTS) behind thin adapters.

## Testing Guidelines
- No test suite yet. If adding:
  - Agent: `pytest` with files `agent/tests/test_*.py`; aim for key-path coverage (STT selection, token handling, DB writes). Run via `uv run pytest`.
  - Web: `vitest` + React Testing Library in `web/__tests__/`. Add `"test": "vitest"` script and run `npm test`.

## Commit & Pull Requests
- Use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`. Example: `feat: add chat transcript view`.
- PRs: concise title, summary of changes, linked issue (if any), screenshots/GIFs for UI, and notes on config/env changes. Keep PRs focused and under ~300 LOC when feasible.

## Security & Configuration
- Never commit secrets. Use `agent/.env.local` and `web/.env.local` for keys: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `OPENAI_API_KEY`, `ELEVEN_API_KEY`, `WISPRFLOW_API_KEY`.
- Avoid committing local artifacts (e.g., `agent/conversations.db`). If generated, add to `.gitignore` or exclude from PRs.
- Principle of least privilege for tokens; rotate when sharing environments.

