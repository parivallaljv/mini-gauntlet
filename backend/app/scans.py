"""Running scans and turning stored findings into summaries."""

import logging
from collections import defaultdict
from typing import Any

from . import config, db
from .scanner import engine
from .schemas import AccountScore, ScanDetail, ScanSummary, SeverityCounts, StatusCounts

logger = logging.getLogger(__name__)


def execute_scan(scan_id: int, account_ids: list[str] | None) -> None:
    """Run in the background: scan, store the findings, mark the scan COMPLETED or FAILED."""
    try:
        inventory = engine.load_inventory(config.inventory_path())
        if account_ids is None:
            account_ids = engine.account_ids(inventory)
            db.set_scan_accounts(scan_id, account_ids)
        findings = engine.run_scan(inventory, account_ids, config.scan_workers())
        db.complete_scan(scan_id, findings)
        logger.info("Scan %s completed with %d findings", scan_id, len(findings))
    except Exception as exc:
        # The whole scan crashed (e.g. the snapshot can't be read): record why.
        logger.exception("Scan %s failed", scan_id)
        db.fail_scan(scan_id, f"{type(exc).__name__}: {exc}")


def summaries() -> list[ScanSummary]:
    """Every scan, newest first, with counts by status and the overall score."""
    counts_by_scan: dict[int, dict[str, int]] = defaultdict(dict)
    for row in db.count_findings(("scan_id", "status")):
        counts_by_scan[row["scan_id"]][row["status"]] = row["n"]
    return [_summary(scan, counts_by_scan[scan["id"]]) for scan in db.list_scans()]


def detail(scan: dict[str, Any]) -> ScanDetail:
    """One scan with counts by status, FAIL counts by severity and per-account scores."""
    scan_id = scan["id"]
    status_counts = {r["status"]: r["n"] for r in db.count_findings(("status",), scan_id)}
    fail_by_severity = {
        r["severity"]: r["n"]
        for r in db.count_findings(("status", "severity"), scan_id)
        if r["status"] == "FAIL"
    }

    per_account: dict[str, dict[str, int]] = defaultdict(dict)
    providers: dict[str, str] = {}
    for row in db.count_findings(("account_id", "provider", "status"), scan_id):
        per_account[row["account_id"]][row["status"]] = row["n"]
        providers[row["account_id"]] = row["provider"]
    # List every account the scan covered, even one that produced no findings.
    account_ids = scan["account_ids"] or list(per_account)

    return ScanDetail(
        **_summary(scan, status_counts).model_dump(),
        fail_by_severity=SeverityCounts(**fail_by_severity),
        accounts=[
            AccountScore(
                account_id=account_id,
                provider=providers.get(account_id),
                score=_score(per_account[account_id]),
                counts=StatusCounts(**per_account[account_id]),
            )
            for account_id in account_ids
        ],
    )


def _summary(scan: dict[str, Any], counts: dict[str, int]) -> ScanSummary:
    return ScanSummary(
        id=scan["id"],
        status=scan["status"],
        started_at=scan["started_at"],
        finished_at=scan["finished_at"],
        account_ids=scan["account_ids"],
        score=_score(counts),
        counts=StatusCounts(**counts),
        error=scan["error"],
    )


def _score(counts: dict[str, int]) -> float | None:
    return engine.score(counts.get("PASS", 0), counts.get("FAIL", 0))
