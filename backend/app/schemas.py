"""Request and response shapes for the API (Pydantic models)."""

from pydantic import BaseModel


class ScanRequest(BaseModel):
    account_ids: list[str] | None = None  # None (or no body) means every account


class StatusCounts(BaseModel):
    PASS: int = 0
    FAIL: int = 0
    CANNOT_SCAN: int = 0


class SeverityCounts(BaseModel):
    CRITICAL: int = 0
    HIGH: int = 0
    MEDIUM: int = 0
    LOW: int = 0


class ScanSummary(BaseModel):
    id: int
    status: str
    started_at: str
    finished_at: str | None
    account_ids: list[str] | None
    score: float | None
    counts: StatusCounts
    error: str | None


class AccountScore(BaseModel):
    account_id: str
    provider: str | None
    score: float | None
    counts: StatusCounts


class ScanDetail(ScanSummary):
    fail_by_severity: SeverityCounts
    accounts: list[AccountScore]


class FindingOut(BaseModel):
    id: int
    scan_id: int
    check_id: str
    title: str
    provider: str
    account_id: str
    region: str | None
    resource_id: str | None
    status: str
    severity: str
    details: str


class FindingsPage(BaseModel):
    items: list[FindingOut]
    total: int
    page: int
    page_size: int


class CheckOut(BaseModel):
    id: str
    title: str
    severity: str
    provider: str
    collection: str
    resource_id_field: str
