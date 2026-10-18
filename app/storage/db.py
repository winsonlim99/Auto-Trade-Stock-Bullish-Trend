import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL);
CREATE TABLE IF NOT EXISTS orders(
 client_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL,
 qty INTEGER NOT NULL CHECK(qty>0), stop REAL NOT NULL CHECK(stop>0),
 state TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fills(
 id INTEGER PRIMARY KEY, client_id TEXT NOT NULL UNIQUE REFERENCES orders(client_id),
 price REAL NOT NULL, qty INTEGER NOT NULL, fee REAL NOT NULL);
CREATE TABLE IF NOT EXISTS positions(
 symbol TEXT PRIMARY KEY, qty INTEGER NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit(
 id INTEGER PRIMARY KEY, at TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT OR IGNORE INTO schema_migrations VALUES(1);
INSERT OR IGNORE INTO account VALUES(1, 10000.0);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone():
                versions = [r[0] for r in db.execute("SELECT version FROM schema_migrations")]
                if any(v != 1 for v in versions):
                    raise ValueError("Unsupported database schema; restore a compatible backup")
            db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, table: str) -> list[dict[str, Any]]:
        if table not in {"account", "orders", "fills", "positions", "audit", "schema_migrations"}:
            raise ValueError("Unknown table")
        with self.connection() as db:
            return [dict(row) for row in db.execute(f"SELECT * FROM {table}")]

    @staticmethod
    def audit(db: sqlite3.Connection, event: str, detail: dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
            (utc_now(), event, json.dumps(detail, sort_keys=True)),
        )

    def backup(self, destination: Path) -> None:
        if destination.resolve() == self.path.resolve() or destination.exists():
            raise ValueError("Backup destination must be a new file")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as source, sqlite3.connect(destination) as target:
            source.backup(target)
