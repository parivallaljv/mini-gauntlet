"""The FastAPI application: routes only; storage is in db.py, scan logic in scans.py."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

from . import config, db, scans
from .scanner import engine
from .scanner.registry import CHECKS
from .schemas import CheckOut, FindingOut, FindingsPage, ScanDetail, ScanRequest, ScanSummary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    db.fail_interrupted_scans()
    yield


app = FastAPI(title="Mini Gauntlet", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/checks")
def list_checks() -> list[CheckOut]:
    return [
        CheckOut(
            id=c.id,
            title=c.title,
            severity=c.severity.value,
            provider=c.provider,
            collection=c.collection,
            resource_id_field=c.id_field,
        )
        for c in CHECKS
    ]


@app.post("/api/scans", status_code=202)
def start_scan(background: BackgroundTasks, body: ScanRequest | None = None) -> ScanSummary:
    account_ids = body.account_ids if body else None
    if account_ids is not None:
        if not account_ids:
            raise HTTPException(422, "account_ids must not be empty; omit it to scan every account")
        account_ids = list(dict.fromkeys(account_ids))  # drop duplicates, keep order
        _reject_unknown_accounts(account_ids)

    scan_id = db.create_scan(account_ids)
    # Runs after the 202 response is sent, in a worker thread.
    background.add_task(scans.execute_scan, scan_id, account_ids)
    return scans.detail(db.get_scan(scan_id))


@app.get("/api/scans")
def list_scans() -> list[ScanSummary]:
    return scans.summaries()


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: int) -> ScanDetail:
    return scans.detail(_scan_or_404(scan_id))


@app.get("/api/scans/{scan_id}/findings")
def list_findings(
    scan_id: int,
    status: str | None = None,
    severity: str | None = None,
    provider: str | None = None,
    account_id: str | None = None,
    check_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> FindingsPage:
    _scan_or_404(scan_id)
    filters = {
        "status": status,
        "severity": severity,
        "provider": provider,
        "account_id": account_id,
        "check_id": check_id,
    }
    rows, total = db.query_findings(scan_id, filters, page, page_size)
    return FindingsPage(
        items=[FindingOut(**row) for row in rows], total=total, page=page, page_size=page_size
    )


def _scan_or_404(scan_id: int) -> dict:
    scan = db.get_scan(scan_id)
    if scan is None:
        raise HTTPException(404, f"Scan {scan_id} not found")
    return scan


def _reject_unknown_accounts(account_ids: list[str]) -> None:
    try:
        known = set(engine.account_ids(engine.load_inventory(config.inventory_path())))
    except Exception:
        # We can't validate against an unreadable snapshot; the scan itself will
        # then fail and be recorded as FAILED with the reason.
        logger.warning("Could not read the inventory to validate account_ids")
        return
    unknown = [a for a in account_ids if a not in known]
    if unknown:
        raise HTTPException(422, f"Unknown account IDs: {', '.join(unknown)}")
