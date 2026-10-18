from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path | None = None) -> dict[str, Any]:
    config = yaml.safe_load((path or ROOT / "config/defaults.yaml").read_text("utf-8"))
    if not isinstance(config, dict):
        raise TypeError("Configuration must be a mapping")
    if config.get("paper_only") is not True or config.get("moomoo_enabled") is not False:
        raise ValueError("Only the offline PAPER_ONLY adapter is supported")
    if config.get("auto_enabled") is not False:
        raise ValueError("Cold startup must be disabled")
    if config.get("initial_equity") != 10000:
        raise ValueError("Milestone 1 local ledger starts at USD 10,000")
    ZoneInfo(config["ui_timezone"])
    ZoneInfo(config["market_timezone"])
    return config
