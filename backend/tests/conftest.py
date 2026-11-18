from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.scanner.models import CannotScan

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "data" / "inventory.json"
SNAPSHOT_TIME = datetime(2026, 10, 1, tzinfo=timezone.utc)


def assert_pass(fn, resource):
    assert fn(resource, SNAPSHOT_TIME) is None


def assert_fail(fn, resource, *expected_in_details):
    details = fn(resource, SNAPSHOT_TIME)
    assert details, "expected FAIL"
    for text in expected_in_details:
        assert text in details
    return details


def assert_cannot_scan(fn, resource, expected_reason=""):
    with pytest.raises(CannotScan) as exc:
        fn(resource, SNAPSHOT_TIME)
    assert expected_reason in str(exc.value)
