# Milestone 1 delivery gate — 2026-10-17

Implemented source groups: `app/config.py`, `app/market/`, `app/execution/`,
`app/storage/`, `app/web/`, `app/check.py`; future-module placeholders;
`config/defaults.yaml`; `samples/daily.csv`; `tests/test_foundation.py`;
Windows install/start scripts; README, example environment and ignore rules.

Verified on Windows with Python 3.13. Tested dependency versions are captured
in `requirements-verified.txt` (development snapshot, not a universal lock).

- Ruff: all checks passed; source formatted.
- Mypy strict: no issues in 15 application source files.
- Pytest: 12 passed. One dependency deprecation warning: current Starlette
  discourages httpx TestClient integration in favor of httpx2; tests still pass.
- Environment check: Python/timezone/config valid, 66 synthetic completed bars.
- Uvicorn: startup complete on loopback, `/` and `/api/health` return HTTP 200.
- All 13 navigation pages render. Session enable returns 409. Startup/restart
  remains OFF. Real account/environment arguments fail before any fill.
- Atomic rollback, durable replay idempotency, conflicting client ID rejection,
  cash validation, stop ratchet persistence, corruption detection and SQLite WAL
  backup exercised by tests.

In this restricted execution environment, TEMP/TMP were pointed to a writable
workspace scratch folder for installation and pytest. Ordinary Windows users
can use their default temp directory.

Remaining limitations are explicit in README and dashboard. Strategy logic,
full risk gates, stop execution, intraday flattening, exchange calendars,
corporate actions, point-in-time universes, backtesting and Moomoo are not
implemented. Risk configuration is not enforcement. The offline broker's
replay accounting helper is not a runnable autonomous trading engine.

Local run: double-click `Install_AutoTrade.bat`, then `Start_AutoTrade.bat`;
open http://127.0.0.1:8000. Exact PowerShell and verification commands are in
README. All execution is local PAPER ONLY; no profitability claims.
