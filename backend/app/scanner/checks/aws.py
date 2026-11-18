"""AWS checks."""

from datetime import datetime, timedelta
from typing import Any

from ..models import CannotScan, Severity
from ..registry import check
from .common import (
    ALL_PORTS,
    INTERNET_CIDRS,
    describe_ports,
    exposed_admin_ports,
    parse_port,
    parse_time,
    require_bool,
    require_list,
)

PUBLIC_ACCESS_BLOCK_FLAGS = (
    "block_public_acls",
    "ignore_public_acls",
    "block_public_policy",
    "restrict_public_buckets",
)
MAX_KEY_AGE = timedelta(days=90)


@check("AWS-S3-01", "S3 bucket blocks public access", Severity.HIGH, "aws", "s3_buckets", "name")
def s3_blocks_public_access(bucket: dict[str, Any], snapshot_time: datetime) -> str | None:
    block = bucket.get("public_access_block")
    # Assumption: null means no public access block is configured at all.
    if block is None:
        return "No public access block is configured on the bucket"
    if not isinstance(block, dict):
        raise CannotScan(f"public_access_block is {block!r}, expected an object")

    disabled = []
    for flag in PUBLIC_ACCESS_BLOCK_FLAGS:
        value = block.get(flag, False)  # a missing flag is not enabled
        if not isinstance(value, bool):
            raise CannotScan(f"public_access_block.{flag} is {value!r}, expected true or false")
        if not value:
            disabled.append(flag)
    if disabled:
        return "Public access block settings are off: " + ", ".join(disabled)
    return None


@check(
    "AWS-EC2-01",
    "Security group doesn't expose SSH or RDP to the internet",
    Severity.CRITICAL,
    "aws",
    "security_groups",
    "group_id",
)
def security_group_admin_ports(group: dict[str, Any], snapshot_time: datetime) -> str | None:
    problems = []
    for rule in require_list(group, "ingress"):
        protocol = str(rule.get("protocol")).lower()
        if protocol == "-1":
            low, high = ALL_PORTS  # "-1" means every protocol and every port
        elif protocol in ("tcp", "6"):  # SSH and RDP run over TCP
            low, high = parse_port(rule.get("from_port")), parse_port(rule.get("to_port"))
        else:
            continue  # UDP, ICMP, ...: can't carry SSH or RDP

        open_cidrs = [cidr for cidr in require_list(rule, "cidrs") if cidr in INTERNET_CIDRS]
        ports = exposed_admin_ports(low, high)
        if open_cidrs and ports:
            problems.append(
                f"Inbound rule protocol {protocol} {describe_ports(low, high)} "
                f"from {', '.join(open_cidrs)} exposes {', '.join(ports)}"
            )
    return "; ".join(problems) or None


@check("AWS-IAM-01", "Console users have MFA", Severity.HIGH, "aws", "iam_users", "user_name")
def console_users_have_mfa(user: dict[str, Any], snapshot_time: datetime) -> str | None:
    if not require_bool(user, "console_access"):
        return None  # no console password, so MFA doesn't apply
    if not require_bool(user, "mfa_enabled"):
        return "User can sign in to the console without MFA"
    return None


@check(
    "AWS-IAM-02",
    "No active access key is older than 90 days",
    Severity.MEDIUM,
    "aws",
    "iam_users",
    "user_name",
)
def access_keys_rotated(user: dict[str, Any], snapshot_time: datetime) -> str | None:
    old_keys = []
    for key in require_list(user, "access_keys"):
        status = key.get("status")
        if not isinstance(status, str):
            raise CannotScan(f"access key status is {status!r}, expected a string")
        if status.lower() != "active":
            continue  # inactive keys can't be used, so their age doesn't matter
        created = parse_time(key.get("created_at"))
        # Age is measured against the snapshot, never the current clock.
        age = snapshot_time - created
        # Strictly greater: a key exactly 90 days old passes.
        if age > MAX_KEY_AGE:
            old_keys.append(
                f"Active key {key.get('key_id')} is {age.days} days old "
                f"(created {created.date().isoformat()})"
            )
    return "; ".join(old_keys) or None


@check(
    "AWS-RDS-01",
    "RDS instance isn't publicly accessible",
    Severity.HIGH,
    "aws",
    "rds_instances",
    "db_instance_id",
)
def rds_not_public(instance: dict[str, Any], snapshot_time: datetime) -> str | None:
    if require_bool(instance, "publicly_accessible"):
        return "Instance is publicly accessible (publicly_accessible is true)"
    return None
