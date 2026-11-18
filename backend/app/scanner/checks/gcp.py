"""Google Cloud checks."""

from datetime import datetime
from typing import Any

from ..models import CannotScan, Severity
from ..registry import check
from .common import (
    ALL_PORTS,
    INTERNET_CIDRS,
    describe_ports,
    exposed_admin_ports,
    parse_port_range,
    require_bool,
    require_list,
)

# allAuthenticatedUsers is any Google account, so it counts as public too.
PUBLIC_MEMBERS = {"allUsers", "allAuthenticatedUsers"}


@check("GCP-GCS-01", "Bucket isn't public", Severity.HIGH, "gcp", "gcs_buckets", "name")
def bucket_not_public(bucket: dict[str, Any], snapshot_time: datetime) -> str | None:
    grants = []
    for binding in require_list(bucket, "iam_bindings"):
        for member in require_list(binding, "members"):
            if member in PUBLIC_MEMBERS:
                grants.append(f"{member} has {binding.get('role')}")
    if grants:
        return "Bucket is public: " + "; ".join(grants)
    return None


@check(
    "GCP-GCS-02",
    "Bucket uses uniform bucket-level access",
    Severity.LOW,
    "gcp",
    "gcs_buckets",
    "name",
)
def bucket_uniform_access(bucket: dict[str, Any], snapshot_time: datetime) -> str | None:
    if not require_bool(bucket, "uniform_bucket_level_access"):
        return "Uniform bucket-level access is off, so object ACLs can grant access"
    return None


@check(
    "GCP-VPC-01",
    "Firewall rule doesn't expose SSH or RDP to the internet",
    Severity.CRITICAL,
    "gcp",
    "firewall_rules",
    "name",
)
def firewall_admin_ports(rule: dict[str, Any], snapshot_time: datetime) -> str | None:
    disabled = rule.get("disabled", False)  # GCP's default is enabled
    if not isinstance(disabled, bool):
        raise CannotScan(f"disabled is {disabled!r}, expected true or false")
    if disabled:
        return None  # a disabled rule lets nothing through
    if str(rule.get("direction", "INGRESS")).upper() != "INGRESS":
        return None  # EGRESS rules don't expose anything to the internet

    problems = []
    for allowed in require_list(rule, "allowed"):
        protocol = str(allowed.get("IPProtocol")).lower()
        if protocol not in ("tcp", "all", "6"):
            continue
        # No "ports" (or protocol "all") means every port.
        port_specs = allowed.get("ports") or []
        if protocol == "all" or not port_specs:
            ranges = [ALL_PORTS]
        else:
            if not isinstance(port_specs, list):
                raise CannotScan(f"ports is {port_specs!r}, expected a list")
            ranges = [parse_port_range(spec) for spec in port_specs]

        open_ranges = [r for r in require_list(rule, "source_ranges") if r in INTERNET_CIDRS]
        if not open_ranges:
            continue
        for low, high in ranges:
            ports = exposed_admin_ports(low, high)
            if ports:
                problems.append(
                    f"Rule allows {protocol} {describe_ports(low, high)} "
                    f"from {', '.join(open_ranges)}, exposing {', '.join(ports)}"
                )

    if not problems:
        return None
    details = "; ".join(problems)
    # Include the rule's own description: it often says why the rule exists.
    # It is untrusted text and is stored and shown as plain text only.
    description = rule.get("description")
    if description:
        details += f". Rule description: {description}"
    return details
