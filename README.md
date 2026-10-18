# AutoTrade V1.0 — Milestone 1

Windows-first **PAPER ONLY** foundation. No live orders, Moomoo connection, strategy engine or enabled automation. The local simulated ledger starts with USD 10,000, separate from any broker simulator.

## Run on Windows

Install Python 3.11+ with the Python launcher. Extract this whole project into a writable folder. Double-click `Install_AutoTrade.bat`, then `Start_AutoTrade.bat`. No administrator access required. Open http://127.0.0.1:8000. Stop using Ctrl+C in the console.

Equivalent PowerShell commands from this folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m app.check
.\.venv\Scripts\python.exe -m uvicorn app.web.main:app --host 127.0.0.1 --port 8000
```

## Verify entirely offline after dependency installation

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use temporary SQLite databases and synthetic CSV data. They need no credentials, network or Moomoo SDK.

## Implemented

- FastAPI/Jinja dashboard with 13 navigation pages, ET and configurable UI timezone (SGT default), explicit unavailable feature panels.
- Safe cold startup, offline data labels and blocked session enable endpoint. No order submission endpoint.
- Completed-at CSV historical data filtering and basic OHLCV validation. Three synthetic ETF series only; no real market coverage claim.
- SQLite WAL, version-1 schema migration, atomic transactions, durable orders/fills/positions/audit and online backup method.
- Offline broker protocol and isolated replay fill accounting, stable client IDs, conflict rejection, adverse illustrative 10bps fill adjustment plus $1 fee, cash validation, restart reconciliation and stop bookkeeping ratchet.
- Rotating JSON event log, environment check, install/start scripts and tests.

## Assumptions and remaining work

The first-action instruction scopes this delivery to milestone 1. Scan/rank, actual risk enforcement, strategies, BPC/BPR lots, partial fills, stop execution, market calendar, splits, backtests and reports belong to milestones 2–4 and 6. Moomoo integration is milestone 5; no SDK calls have been fabricated or included. Its exact API, account permissions and paper order support must be verified then.

Risk defaults are configuration only, not active enforcement. Accordingly **all normal entries are rejected**, including from the UI. `record_replay_fill` is a fixture accounting helper, never a trading signal or UI path; it is not the final realistic fill engine. Protection values are ledger metadata, not working protective orders. Session activation remains unavailable until protective/risk/data gates exist.

Sample CSV is explicitly synthetic, dated January 2025, weekday-only (not exchange calendar validated), unadjusted, and stale for current trading. It must never authorize a current session. No profitability claims or strategy results exist.

Replay reconciliation compares local durable accounting records; there is no external broker source yet. A future adapter must independently reconcile broker positions, orders and fills. Intraday cutoff, real calendar/DST edge cases and stop gap/split behavior are not implemented in this milestone.

## Backup and restore

While running, use SQLite's backup API via `Store.backup(Path(...))`; never copy only the main database while WAL is active. To restore, stop AutoTrade, preserve the entire existing runtime folder, then place a verified backup database in a **new empty runtime folder** as `autotrade.db`. Start again; cold startup is OFF and reconciliation runs. Never overwrite an active database. Logs and databases are git-ignored; do not commit credentials.

Optional service installation is deferred. The console launch intentionally makes shutdown and errors visible. Do not expose this unauthenticated local foundation to a network or add a service that silently restarts a trading session.

Stops cannot guarantee a fill. Future app-managed stops will fail while the computer or connection is down. This release is not live-trading ready.
