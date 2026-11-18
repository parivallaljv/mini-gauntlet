"""Azure checks."""

from datetime import datetime
from typing import Any

from ..models import CannotScan, Severity
from ..registry import check
from .common import (
    INTERNET_CIDRS,
    describe_ports,
    exposed_admin_ports,
    parse_port_range,
    require_bool,
    require_list,
)

# NSG sources that mean "anyone on the internet". Compared in lower case.
INTERNET_SOURCES = {"*", "internet", "any"} | INTERNET_CIDRS


@check(
    "AZ-STG-01",
    "Storage account blocks public blob access",
    Severity.HIGH,
    "azure",
    "storage_accounts",
    "name",
)
def storage_blocks_public_blobs(account: dict[str, Any], snapshot_time: datetime) -> str | None:
    if require_bool(account, "allow_blob_public_access"):
        return "allow_blob_public_access is true, so containers can be made public"
    return None


@check(
    "AZ-NSG-01",
    "NSG doesn't expose SSH or RDP to the internet",
    Severity.CRITICAL,
    "azure",
    "network_security_groups",
    "name",
)
def nsg_admin_ports(nsg: dict[str, Any], snapshot_time: datetime) -> str | None:
    problems = []
    for rule in require_list(nsg, "rules"):
        # Only inbound Allow rules can expose anything; Deny and Outbound never FAIL.
        if str(rule.get("direction")).lower() != "inbound":
            continue
        if str(rule.get("access")).lower() != "allow":
            continue
        protocol = str(rule.get("protocol")).lower()
        if protocol not in ("tcp", "*"):  # "*" means any protocol
            continue

        ports_field = rule.get("destination_ports")
        # Accept "22", "3380-3400", "*", "22,3389" or a list of those.
        if isinstance(ports_field, str):
            parts = ports_field.split(",")
        elif isinstance(ports_field, list):
            parts = ports_field
        else:
            raise CannotScan(f"destination_ports is {ports_field!r}, expected a string")
        ranges = [parse_port_range(part) for part in parts]

        source = rule.get("source")
        if str(source).lower() not in INTERNET_SOURCES:
            continue
        for low, high in ranges:
            ports = exposed_admin_ports(low, high)
            if ports:
                problems.append(
                    f"Rule {rule.get('name')!r} allows protocol {rule.get('protocol')} "
                    f"{describe_ports(low, high)} from {source}, exposing {', '.join(ports)}"
                )
    return "; ".join(problems) or None
