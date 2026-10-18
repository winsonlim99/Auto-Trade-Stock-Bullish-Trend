import math
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.storage.db import Store, utc_now

PAPER_ONLY = True


@dataclass(frozen=True)
class PaperOrder:
    client_id: str
    symbol: str
    qty: int
    stop: float
    environment: Literal["SIMULATE"] = "SIMULATE"
    account_id: str = "LOCAL-PAPER"


class BrokerAdapter(Protocol):
    def get_capabilities(self) -> dict[str, Any]: ...
    def connect(self) -> None: ...
    def health(self) -> dict[str, Any]: ...
    def get_account(self) -> dict[str, Any]: ...
    def get_positions(self) -> list[dict[str, Any]]: ...
    def get_orders(self) -> list[dict[str, Any]]: ...
    def get_fills(self) -> list[dict[str, Any]]: ...
    def place_paper_order(self, order: PaperOrder) -> str: ...
    def cancel_paper_order(self, client_id: str) -> None: ...
    def update_protection_if_supported(self, symbol: str, stop: float) -> None: ...
    def reconcile(self) -> bool: ...


class OfflinePaperBroker:
    """Isolated replay broker. No network calls or real broker identifiers accepted.

    Milestone 1 has no entry authorization path: order submission always fails closed.
    Replay fills exist only to exercise durable accounting in offline tests.
    """

    def __init__(self, store: Store):
        self.store = store
        self.connected = False
        self.reconciled = False

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "paper_only": PAPER_ONLY,
            "adapter": "OFFLINE",
            "live_orders": False,
            "entries": False,
            "replay_fill_tests": True,
            "broker_stops": False,
            "app_stops": "Not running in milestone 1; connection dependent when implemented",
        }

    def connect(self) -> None:
        self.connected = True
        self.reconcile()

    def health(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "reconciled": self.reconciled,
            "entries_allowed": False,
            "reason": "Milestone 1: historical data and no risk engine",
        }

    def get_account(self) -> dict[str, Any]:
        return {
            **self.store.rows("account")[0],
            "account_id": "LOCAL-PAPER",
            "initial_equity": 10000,
            "currency": "USD",
            "broker_balance": None,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        return self.store.rows("positions")

    def get_orders(self) -> list[dict[str, Any]]:
        return self.store.rows("orders")

    def get_fills(self) -> list[dict[str, Any]]:
        return self.store.rows("fills")

    def place_paper_order(self, order: PaperOrder) -> str:
        if order.environment != "SIMULATE" or order.account_id != "LOCAL-PAPER":
            raise ValueError("Real or external accounts are forbidden")
        raise RuntimeError("Entries disabled until risk, data and protection gates are implemented")

    def record_replay_fill(self, order: PaperOrder, reference: float) -> str:
        """Test/replay fixture only, never connected to a route or automation loop."""
        if order.environment != "SIMULATE" or order.account_id != "LOCAL-PAPER":
            raise ValueError("Real or external accounts are forbidden")
        if not self.connected or not self.reconciled:
            raise RuntimeError("Connect and reconcile before replay")
        if (
            not order.client_id
            or not order.symbol
            or type(order.qty) is not int
            or order.qty <= 0
            or not all(math.isfinite(v) and v > 0 for v in (reference, order.stop))
            or order.stop >= reference
        ):
            raise ValueError("Invalid long order or protective stop")
        # Fixed illustrative spread/slippage: adverse 10bps, plus $1 fee.
        price = round(reference * 1.001, 4)
        cost = price * order.qty + 1
        with self.store.connection() as db:
            existing = db.execute(
                "SELECT * FROM orders WHERE client_id=?", (order.client_id,)
            ).fetchone()
            if existing:
                if (existing["symbol"], existing["qty"], existing["stop"]) != (
                    order.symbol,
                    order.qty,
                    order.stop,
                ):
                    raise ValueError("Client ID reused with conflicting payload")
                return str(existing["state"])
            if db.execute("SELECT 1 FROM positions WHERE symbol=?", (order.symbol,)).fetchone():
                raise ValueError("Duplicate symbol; reload unsupported")
            cash = float(db.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])
            if cost > cash:
                raise ValueError("Insufficient local cash")
            db.execute(
                "INSERT INTO orders VALUES(?,?,?,?,?,?,?)",
                (order.client_id, order.symbol, "BUY", order.qty, order.stop, "FILLED", utc_now()),
            )
            db.execute(
                "INSERT INTO fills(client_id,price,qty,fee) VALUES(?,?,?,?)",
                (order.client_id, price, order.qty, 1),
            )
            db.execute(
                "INSERT INTO positions VALUES(?,?,?,?)",
                (order.symbol, order.qty, price, order.stop),
            )
            db.execute("UPDATE account SET cash=cash-? WHERE id=1", (cost,))
            Store.audit(db, "REPLAY_FILL", {"client_id": order.client_id, "price": price})
        return "FILLED"

    def cancel_paper_order(self, client_id: str) -> None:
        with self.store.connection() as db:
            order = db.execute(
                "SELECT state FROM orders WHERE client_id=?", (client_id,)
            ).fetchone()
            if order is None:
                raise ValueError("Unknown order; reconciliation required")
            if order[0] == "FILLED":
                raise ValueError("Cannot cancel a completed fill")
            raise RuntimeError("Pending orders unsupported in milestone 1")

    def update_protection_if_supported(self, symbol: str, stop: float) -> None:
        if not math.isfinite(stop) or stop <= 0:
            raise ValueError("Invalid stop")
        # Bookkeeping only, explicitly not an executable protective order.
        with self.store.connection() as db:
            row = db.execute("SELECT stop FROM positions WHERE symbol=?", (symbol,)).fetchone()
            if row is None or stop < row[0]:
                Store.audit(db, "STOP_UPDATE_FAILED", {"symbol": symbol})
            else:
                db.execute("UPDATE positions SET stop=? WHERE symbol=?", (stop, symbol))
                Store.audit(db, "REPLAY_STOP_RATCHET", {"symbol": symbol, "stop": stop})
                return
        raise ValueError("Missing position or decreasing stop")

    def reconcile(self) -> bool:
        with self.store.connection() as db:
            bad = db.execute(
                "SELECT COUNT(*) FROM orders o LEFT JOIN fills f USING(client_id) "
                "WHERE o.state!='FILLED' OR f.id IS NULL"
            ).fetchone()[0]
            expected = (
                10000 - db.execute("SELECT COALESCE(SUM(price*qty+fee),0) FROM fills").fetchone()[0]
            )
            cash = db.execute("SELECT cash FROM account WHERE id=1").fetchone()[0]
            positions = {r["symbol"]: r["qty"] for r in db.execute("SELECT * FROM positions")}
            filled = {
                r[0]: r[1]
                for r in db.execute(
                    "SELECT o.symbol,SUM(f.qty) FROM fills f JOIN orders o USING(client_id) "
                    "GROUP BY o.symbol"
                )
            }
            self.reconciled = bool(
                self.connected and not bad and abs(cash - expected) < 0.0001 and positions == filled
            )
            Store.audit(db, "RECONCILE", {"ok": self.reconciled, "source": "local replay ledger"})
        return self.reconciled
