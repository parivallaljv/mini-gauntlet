"""Settings from environment variables.

They are read on every call (not at import time) so tests can change them.
"""

import os
from pathlib import Path

# data/inventory.json at the repo root, for running locally without any env vars.
_DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "data" / "inventory.json"


def db_path() -> str:
    return os.environ.get("DB_PATH", "mini_gauntlet.db")


def inventory_path() -> str:
    return os.environ.get("INVENTORY_PATH", str(_DEFAULT_INVENTORY))


def scan_workers() -> int:
    return max(1, int(os.environ.get("SCAN_WORKERS", "4")))
