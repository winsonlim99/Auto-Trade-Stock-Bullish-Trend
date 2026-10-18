import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Bar:
    symbol: str
    at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class DataProvider(Protocol):
    def history(self, symbol: str, as_of: datetime) -> list[Bar]: ...
    def quality(self) -> dict[str, str]: ...


class CsvProvider:
    def __init__(self, path: Path):
        self.bars: list[Bar] = []
        with path.open(newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                bar = Bar(
                    row["symbol"],
                    datetime.fromisoformat(row["completed_at"]),
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    int(row["volume"]),
                )
                if (
                    bar.at.tzinfo is None
                    or not all(
                        math.isfinite(v) and v > 0 for v in (bar.open, bar.high, bar.low, bar.close)
                    )
                    or not (
                        bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high
                    )
                    or bar.volume < 0
                ):
                    raise ValueError("Invalid OHLCV or timezone")
                self.bars.append(bar)
        keys = [(b.symbol, b.at) for b in self.bars]
        if len(keys) != len(set(keys)) or not keys:
            raise ValueError("Empty or duplicate market data")
        self.bars.sort(key=lambda b: (b.symbol, b.at))

    def history(self, symbol: str, as_of: datetime) -> list[Bar]:
        if as_of.tzinfo is None:
            raise ValueError("Timezone-aware replay clock required")
        return [b for b in self.bars if b.symbol == symbol and b.at <= as_of]

    def quality(self) -> dict[str, str]:
        return {
            "mode": "SYNTHETIC / OFFLINE",
            "entries": "BLOCKED: historical fixture only",
            "coverage": "Three synthetic ETF series; not a complete US universe",
            "rights": "No real-time quotes, entitlements or subscriptions",
            "calendar": "Fixture timestamps only; exchange calendar not implemented",
            "corporate_actions": "Unavailable; not split-adjusted",
        }
