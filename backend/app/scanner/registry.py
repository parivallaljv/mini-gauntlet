"""The check registry.

A check is a plain function decorated with @check(...). The decorator records the
check's metadata and adds it to CHECKS; the engine runs whatever is in CHECKS.

A check function receives one resource (a dict from the snapshot) and the snapshot
time, and must either:
  - return None            -> PASS
  - return a string        -> FAIL, the string is the finding's details
  - raise CannotScan(why)  -> CANNOT_SCAN
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import Severity

CheckFn = Callable[[dict[str, Any], datetime], str | None]


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    severity: Severity
    provider: str  # "aws", "azure" or "gcp"
    collection: str  # key under account["resources"], e.g. "s3_buckets"
    id_field: str  # field of the resource used as its resource_id
    fn: CheckFn


CHECKS: list[Check] = []


def check(
    id: str, title: str, severity: Severity, provider: str, collection: str, id_field: str
) -> Callable[[CheckFn], CheckFn]:
    """Decorator that registers a check function."""

    def register(fn: CheckFn) -> CheckFn:
        if any(c.id == id for c in CHECKS):
            raise ValueError(f"Duplicate check id: {id}")
        CHECKS.append(Check(id, title, severity, provider, collection, id_field, fn))
        return fn

    return register
