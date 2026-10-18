import sys
from zoneinfo import ZoneInfo

from app.config import ROOT, load_config
from app.market.data import CsvProvider


def main() -> None:
    if sys.version_info < (3, 11):  # noqa: UP036 - useful when run directly
        raise RuntimeError("Python 3.11+ required")
    load_config()
    ZoneInfo("America/New_York")
    provider = CsvProvider(ROOT / "samples/daily.csv")
    print(f"OK: Python, timezone data, safe config, {len(provider.bars)} synthetic bars")
    print("PAPER ONLY; cold startup OFF; current data and execution unavailable")


if __name__ == "__main__":
    main()
