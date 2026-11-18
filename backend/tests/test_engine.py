import dataclasses
import logging
import time
from collections import Counter

import pytest

from app.scanner.engine import load_inventory, run_scan, scan_account, score
from app.scanner.models import Severity, Status
from app.scanner.registry import CHECKS, check

from .conftest import INVENTORY_PATH, SNAPSHOT_TIME

PROD, DEV = "123456789012", "210987654321"
AZURE, GCP = "8f14e45f-ceea-4e7a-9d3b-2f6c1a0b7d21", "example-corp-gcp"


@pytest.fixture(scope="module")
def full_scan():
    """Scan the real snapshot once (about 3 seconds) and share the result."""
    inventory = load_inventory(str(INVENTORY_PATH))
    start = time.perf_counter()
    findings = run_scan(inventory, workers=4)
    return findings, time.perf_counter() - start


def counts(findings):
    return Counter(f.status for f in findings)


def score_of(findings):
    c = counts(findings)
    return score(c[Status.PASS], c[Status.FAIL])


# --- Acceptance numbers for data/inventory.json -------------------------------


def test_acceptance_status_counts(full_scan):
    findings, _ = full_scan
    assert len(findings) == 49
    assert counts(findings) == {Status.PASS: 27, Status.FAIL: 18, Status.CANNOT_SCAN: 4}


def test_acceptance_overall_score(full_scan):
    findings, _ = full_scan
    assert score_of(findings) == 60.0


@pytest.mark.parametrize(
    ("account_id", "expected"), [(PROD, 58.3), (DEV, 66.7), (AZURE, 57.1), (GCP, 63.6)]
)
def test_acceptance_score_per_account(full_scan, account_id, expected):
    findings, _ = full_scan
    assert score_of([f for f in findings if f.account_id == account_id]) == expected


def test_acceptance_fail_by_severity(full_scan):
    findings, _ = full_scan
    by_severity = Counter(f.severity for f in findings if f.status == Status.FAIL)
    assert by_severity == {
        Severity.CRITICAL: 7,
        Severity.HIGH: 8,
        Severity.MEDIUM: 2,
        Severity.LOW: 1,
    }


def test_acceptance_full_scan_is_concurrent(full_scan):
    _, elapsed = full_scan
    # Latencies are 1.5 + 3 + 1 + 2.5 = 8 s in sequence; with 4 workers the slowest (3 s) wins.
    assert 2.9 <= elapsed < 4.5


def test_acceptance_cannot_scan_findings(full_scan):
    findings, _ = full_scan
    cannot = sorted(
        (f.check_id, f.resource_id, f.details) for f in findings if f.status == Status.CANNOT_SCAN
    )
    assert cannot == [
        (
            "AWS-EC2-01",
            "sg-0b1c2d3e4f5a60002",
            "Cannot evaluate: port 'twenty-two' is not a number",
        ),
        ("AWS-IAM-01", None, "Could not read iam_users: AccessDenied"),
        ("AWS-IAM-02", None, "Could not read iam_users: AccessDenied"),
        ("AWS-RDS-01", None, "Could not read rds_instances: UnauthorizedOperation"),
    ]


# --- Engine rules -------------------------------------------------------------


def account(provider="aws", latency=0, errors=None, **resources):
    return {
        "provider": provider,
        "account_id": "acct-1",
        "simulated_latency_ms": latency,
        "errors": errors or {},
        "resources": resources,
    }


def test_collection_in_errors_gives_one_cannot_scan_per_check():
    findings = scan_account(account(errors={"iam_users": "AccessDenied"}), SNAPSHOT_TIME)
    assert [(f.check_id, f.status, f.resource_id) for f in findings] == [
        ("AWS-IAM-01", Status.CANNOT_SCAN, None),
        ("AWS-IAM-02", Status.CANNOT_SCAN, None),
    ]
    assert all("AccessDenied" in f.details for f in findings)


def test_missing_collection_gives_no_findings():
    assert scan_account(account(), SNAPSHOT_TIME) == []


def test_checks_only_run_for_their_provider():
    # An Azure account with an AWS-shaped collection is ignored by AWS checks.
    bucket = {"name": "b", "public_access_block": None}
    assert scan_account(account(provider="azure", s3_buckets=[bucket]), SNAPSHOT_TIME) == []


def test_finding_carries_region_and_resource_id():
    rds = [{"db_instance_id": "db-1", "region": "eu-west-1", "publicly_accessible": True}]
    (finding,) = scan_account(account(rds_instances=rds), SNAPSHOT_TIME)
    assert (finding.resource_id, finding.region, finding.status) == ("db-1", "eu-west-1", "FAIL")
    assert finding.title == "RDS instance isn't publicly accessible"
    assert finding.severity == Severity.HIGH


def test_bad_record_is_cannot_scan_logs_a_warning_and_scan_continues(caplog):
    rds = [
        "not-an-object",
        {"db_instance_id": "db-bad"},  # missing publicly_accessible
        {"db_instance_id": "db-ok", "publicly_accessible": False},
    ]
    with caplog.at_level(logging.WARNING):
        findings = scan_account(account(rds_instances=rds), SNAPSHOT_TIME)
    assert [f.status for f in findings] == [Status.CANNOT_SCAN, Status.CANNOT_SCAN, Status.PASS]
    assert "db-bad" in caplog.text


def test_crashing_check_does_not_stop_the_scan():
    def boom(resource, snapshot_time):
        raise RuntimeError("bug in check")

    index = next(i for i, c in enumerate(CHECKS) if c.id == "AWS-RDS-01")
    original = CHECKS[index]
    CHECKS[index] = dataclasses.replace(original, fn=boom)
    try:
        rds = [{"db_instance_id": "db-1", "publicly_accessible": True}]
        users = [{"user_name": "u", "console_access": False, "access_keys": []}]
        findings = scan_account(account(rds_instances=rds, iam_users=users), SNAPSHOT_TIME)
    finally:
        CHECKS[index] = original
    by_check = {f.check_id: f for f in findings}
    assert by_check["AWS-RDS-01"].status == Status.CANNOT_SCAN
    assert "RuntimeError" in by_check["AWS-RDS-01"].details
    assert by_check["AWS-IAM-01"].status == Status.PASS


def test_broken_account_does_not_stop_other_accounts():
    inventory = {
        "snapshot_taken_at": "2026-10-01T00:00:00Z",
        "accounts": [
            {**account(), "account_id": "broken", "errors": "not-a-dict"},
            {**account(rds_instances=[{"db_instance_id": "db", "publicly_accessible": False}])},
        ],
    }
    findings = run_scan(inventory)
    assert {(f.account_id, f.status) for f in findings if f.account_id == "acct-1"} == {
        ("acct-1", Status.PASS)
    }
    broken = [f for f in findings if f.account_id == "broken"]
    assert broken and all(f.status == Status.CANNOT_SCAN for f in broken)


def test_only_selected_accounts_are_scanned():
    inventory = load_inventory(str(INVENTORY_PATH))
    for a in inventory["accounts"]:
        a["simulated_latency_ms"] = 0  # a modified in-memory copy, the file is untouched
    findings = run_scan(inventory, only_accounts=[AZURE])
    assert {f.account_id for f in findings} == {AZURE}
    assert len(findings) == 7


def test_worker_limit_is_respected():
    inventory = {
        "snapshot_taken_at": "2026-10-01T00:00:00Z",
        "accounts": [{**account(latency=200), "account_id": str(i)} for i in range(4)],
    }
    start = time.perf_counter()
    run_scan(inventory, workers=4)
    parallel = time.perf_counter() - start

    start = time.perf_counter()
    run_scan(inventory, workers=1)
    serial = time.perf_counter() - start

    assert parallel < 0.5  # all four sleep at the same time
    assert serial >= 0.8  # one at a time: 4 x 0.2 s


def test_snapshot_time_drives_age_rules_not_the_clock():
    users = [
        {
            "user_name": "u",
            "console_access": False,
            "access_keys": [
                {"key_id": "k", "status": "Active", "created_at": "2026-01-01T00:00:00Z"}
            ],
        }
    ]
    inventory = {
        "snapshot_taken_at": "2026-02-01T00:00:00Z",  # key is 31 days old at snapshot time
        "accounts": [account(iam_users=users)],
    }
    by_check = {f.check_id: f.status for f in run_scan(inventory)}
    assert by_check["AWS-IAM-02"] == Status.PASS


def test_load_inventory_rejects_wrong_shape(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"accounts": "nope"}')
    with pytest.raises(ValueError):
        load_inventory(str(path))


# --- Registry and scoring ---------------------------------------------------


def test_registry_has_the_ten_catalog_checks():
    assert sorted(c.id for c in CHECKS) == [
        "AWS-EC2-01",
        "AWS-IAM-01",
        "AWS-IAM-02",
        "AWS-RDS-01",
        "AWS-S3-01",
        "AZ-NSG-01",
        "AZ-STG-01",
        "GCP-GCS-01",
        "GCP-GCS-02",
        "GCP-VPC-01",
    ]


def test_registering_a_check_needs_no_other_changes():
    @check("TEST-01", "Test check", Severity.LOW, "aws", "rds_instances", "db_instance_id")
    def always_fails(resource, snapshot_time):
        return "always fails"

    try:
        rds = [{"db_instance_id": "db", "publicly_accessible": False}]
        findings = scan_account(account(rds_instances=rds), SNAPSHOT_TIME)
        assert ("TEST-01", Status.FAIL) in {(f.check_id, f.status) for f in findings}
    finally:
        CHECKS[:] = [c for c in CHECKS if c.id != "TEST-01"]


def test_duplicate_check_id_is_rejected():
    with pytest.raises(ValueError):
        check("AWS-S3-01", "dup", Severity.LOW, "aws", "s3_buckets", "name")(lambda r, t: None)


@pytest.mark.parametrize(
    ("passed", "failed", "expected"),
    [(0, 0, None), (1, 0, 100.0), (0, 3, 0.0), (2, 1, 66.7), (28, 17, 62.2)],
)
def test_score(passed, failed, expected):
    assert score(passed, failed) == expected
