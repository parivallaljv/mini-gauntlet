"""Runs every registered check over every account in a snapshot."""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from . import checks  # noqa: F401  (importing the package registers every check)
from .checks.common import parse_time
from .models import CannotScan, Finding, Status
from .registry import CHECKS, Check

logger = logging.getLogger(__name__)


def load_inventory(path: str) -> dict[str, Any]:
    """Read and minimally validate the snapshot. Any error here fails the whole scan."""
    with open(path, encoding="utf-8") as f:
        inventory = json.load(f)
    if not isinstance(inventory, dict) or not isinstance(inventory.get("accounts"), list):
        raise ValueError("inventory must be an object with an 'accounts' list")
    return inventory


def account_ids(inventory: dict[str, Any]) -> list[str]:
    return [str(a.get("account_id")) for a in inventory["accounts"] if isinstance(a, dict)]


def score(passed: int, failed: int) -> float | None:
    """100 * PASS / (PASS + FAIL) to one decimal. CANNOT_SCAN is left out.

    Returns None when there is nothing to score (the dashboard shows "N/A").
    """
    if passed + failed == 0:
        return None
    return round(100 * passed / (passed + failed), 1)


def run_scan(
    inventory: dict[str, Any], only_accounts: list[str] | None = None, workers: int = 4
) -> list[Finding]:
    """Scan the selected accounts (all if None) concurrently, at most `workers` at a time."""
    snapshot_time = parse_time(inventory.get("snapshot_taken_at"))
    accounts = [
        a
        for a in inventory["accounts"]
        if isinstance(a, dict) and (only_accounts is None or a.get("account_id") in only_accounts)
    ]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_account = pool.map(lambda a: _scan_account_safely(a, snapshot_time), accounts)
        return [finding for findings in per_account for finding in findings]


def _scan_account_safely(account: dict[str, Any], snapshot_time: datetime) -> list[Finding]:
    # Last line of defence: a broken account record must not stop the other accounts.
    try:
        return scan_account(account, snapshot_time)
    except Exception as exc:
        logger.warning("Account %r could not be scanned: %r", account.get("account_id"), exc)
        return [
            _account_level_finding(chk, account, f"Account could not be scanned: {exc}")
            for chk in CHECKS
            if chk.provider == account.get("provider")
        ]


def scan_account(account: dict[str, Any], snapshot_time: datetime) -> list[Finding]:
    """Run every check for the account's provider and return one finding per resource."""
    # Stands in for the time real cloud API calls would take.
    time.sleep(_latency_seconds(account))

    errors = account.get("errors") or {}
    resources = account.get("resources") or {}
    if not isinstance(errors, dict) or not isinstance(resources, dict):
        raise ValueError("'errors' and 'resources' must be objects")
    findings = []
    for chk in CHECKS:
        if chk.provider != account.get("provider"):
            continue
        if chk.collection in errors:
            # The collection couldn't be read: one finding for the account, no resource ID.
            reason = f"Could not read {chk.collection}: {errors[chk.collection]}"
            findings.append(_account_level_finding(chk, account, reason))
            continue
        collection = resources.get(chk.collection, [])  # missing collection => no findings
        if not isinstance(collection, list):
            reason = f"{chk.collection} is not a list"
            findings.append(_account_level_finding(chk, account, reason))
            continue
        for resource in collection:
            findings.append(_evaluate(chk, account, resource, snapshot_time))
    return findings


def _evaluate(
    chk: Check, account: dict[str, Any], resource: Any, snapshot_time: datetime
) -> Finding:
    """Run one check on one resource. Never raises: problems become CANNOT_SCAN."""
    resource_id = region = None
    try:
        if not isinstance(resource, dict):
            raise CannotScan("resource is not an object")
        resource_id = _optional_str(resource.get(chk.id_field))
        region = _optional_str(resource.get("region"))
        details = chk.fn(resource, snapshot_time)
        status = Status.FAIL if details else Status.PASS
        details = details or "Passed"
    except CannotScan as exc:
        logger.warning("%s cannot scan %r: %s", chk.id, resource_id, exc)
        status, details = Status.CANNOT_SCAN, f"Cannot evaluate: {exc}"
    except Exception as exc:
        # A bug in a check or a very odd record: log it and carry on with the scan.
        logger.warning("%s crashed on %r: %r", chk.id, resource_id, exc)
        status, details = Status.CANNOT_SCAN, f"Check failed on this record: {type(exc).__name__}"

    return Finding(
        check_id=chk.id,
        title=chk.title,
        provider=chk.provider,
        account_id=str(account.get("account_id")),
        region=region,
        resource_id=resource_id,
        status=status,
        severity=chk.severity,
        details=details,
    )


def _account_level_finding(chk: Check, account: dict[str, Any], details: str) -> Finding:
    return Finding(
        check_id=chk.id,
        title=chk.title,
        provider=chk.provider,
        account_id=str(account.get("account_id")),
        region=None,
        resource_id=None,
        status=Status.CANNOT_SCAN,
        severity=chk.severity,
        details=details,
    )


def _latency_seconds(account: dict[str, Any]) -> float:
    latency = account.get("simulated_latency_ms", 0)
    if isinstance(latency, bool) or not isinstance(latency, (int, float)) or latency < 0:
        logger.warning("Ignoring bad simulated_latency_ms %r", latency)
        return 0.0
    return latency / 1000


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
