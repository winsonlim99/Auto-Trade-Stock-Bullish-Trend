from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT
from app.execution.broker import OfflinePaperBroker, PaperOrder
from app.market.data import CsvProvider
from app.storage.db import Store
from app.web.main import PAGES, create_app


def broker_at(path: Path) -> OfflinePaperBroker:
    broker = OfflinePaperBroker(Store(path))
    broker.connect()
    return broker


def test_dashboard_cold_start_and_every_page(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path)) as client:
        for page in PAGES:
            response = client.get(f"/page/{page}")
            assert response.status_code == 200
            assert "SESSION OFF" in response.text
        assert client.get("/api/health").json()["session_enabled"] is False
        assert client.post("/api/session/enable").status_code == 409
        assert client.get("/page/invalid").status_code == 404
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/health").json()["session_enabled"] is False


def test_ledger_restart_idempotency_and_stop_ratchet(tmp_path: Path) -> None:
    path = tmp_path / "test.db"
    broker = broker_at(path)
    order = PaperOrder("stable-1", "SPY", 2, 90)
    assert broker.record_replay_fill(order, 100) == "FILLED"
    assert broker.record_replay_fill(order, 100) == "FILLED"
    assert len(broker.get_fills()) == 1
    assert broker.get_account()["cash"] == pytest.approx(9798.8)
    with pytest.raises(ValueError, match="conflicting"):
        broker.record_replay_fill(replace(order, qty=3), 100)
    broker.update_protection_if_supported("SPY", 95)
    with pytest.raises(ValueError):
        broker.update_protection_if_supported("SPY", 94)
    recovered = broker_at(path)
    assert recovered.reconciled
    assert recovered.get_positions()[0]["stop"] == 95
    assert len(recovered.get_fills()) == 1


@pytest.mark.parametrize("change", [{"environment": "REAL"}, {"account_id": "12345"}])
def test_real_boundary(tmp_path: Path, change: dict[str, str]) -> None:
    broker = broker_at(tmp_path / "test.db")
    order = PaperOrder("x", "SPY", 1, 90)
    for method in (broker.place_paper_order, lambda o: broker.record_replay_fill(o, 100)):
        with pytest.raises(ValueError):
            method(replace(order, **change))  # type: ignore[arg-type]


def test_entries_fail_closed_and_disconnect(tmp_path: Path) -> None:
    broker = OfflinePaperBroker(Store(tmp_path / "test.db"))
    order = PaperOrder("x", "SPY", 1, 90)
    with pytest.raises(RuntimeError):
        broker.record_replay_fill(order, 100)
    broker.connect()
    with pytest.raises(RuntimeError, match="Entries disabled"):
        broker.place_paper_order(order)
    assert broker.get_orders() == []


@pytest.mark.parametrize(
    "qty,stop,price", [(0, 90, 100), (1, 101, 100), (1, 90, float("nan")), (1000, 90, 100)]
)
def test_invalid_replay_atomic(tmp_path: Path, qty: int, stop: float, price: float) -> None:
    broker = broker_at(tmp_path / "test.db")
    with pytest.raises(ValueError):
        broker.record_replay_fill(PaperOrder("x", "SPY", qty, stop), price)
    assert broker.get_account()["cash"] == 10000
    assert broker.get_fills() == []


def test_reconciliation_detects_corruption(tmp_path: Path) -> None:
    broker = broker_at(tmp_path / "test.db")
    with broker.store.connection() as db:
        db.execute("UPDATE account SET cash=9999")
    assert not broker.reconcile()
    with pytest.raises(RuntimeError):
        broker.record_replay_fill(PaperOrder("x", "SPY", 1, 90), 100)


def test_wal_backup_and_transaction_rollback(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    with pytest.raises(RuntimeError), store.connection() as db:
        db.execute("UPDATE account SET cash=1")
        raise RuntimeError("simulated crash before commit")
    assert store.rows("account")[0]["cash"] == 10000
    with store.connection() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    store.backup(tmp_path / "backup.db")
    assert Store(tmp_path / "backup.db").rows("account")[0]["cash"] == 10000


def test_completed_bars_only_and_coverage() -> None:
    data = CsvProvider(ROOT / "samples/daily.csv")
    clock = datetime(2025, 1, 7, 20, tzinfo=UTC)
    bars = data.history("SPY", clock)
    assert len(bars) == 1
    assert all(b.at <= clock for b in bars)
    assert "BLOCKED" in data.quality()["entries"]
    with pytest.raises(ValueError):
        data.history("SPY", datetime(2025, 1, 7))
