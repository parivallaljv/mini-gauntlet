"""Data types shared by the scanner, the checks and the API."""

from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    CANNOT_SCAN = "CANNOT_SCAN"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CannotScan(Exception):
    """Raised by a check when a resource's fields can't be evaluated."""


@dataclass
class Finding:
    check_id: str
    title: str
    provider: str
    account_id: str
    region: str | None
    resource_id: str | None
    status: Status
    severity: Severity
    details: str
