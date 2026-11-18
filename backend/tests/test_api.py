import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

from .conftest import INVENTORY_PATH

AZURE, GCP = "8f14e45f-ceea-4e7a-9d3b-2f6c1a0b7d21", "example-corp-gcp"
STATUS_RANK = {"FAIL": 0, "CANNOT_SCAN": 1, "PASS": 2}
SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@pytest.fixture
def fast_inventory(tmp_path):
    """A copy of data/inventory.json with no simulated latency, so API tests are quick."""
    inventory = json.loads(INVENTORY_PATH.read_text())
    for account in inventory["accounts"]:
        account["simulated_latency_ms"] = 0
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory))
    return path


@pytest.fixture
def client(tmp_path, monkeypatch, fast_inventory):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "db" / "test.db"))
    monkeypatch.setenv("INVENTORY_PATH", str(fast_inventory))
    with TestClient(app) as test_client:  # "with" runs the startup code
        yield test_client


@pytest.fixture
def scan_id(client):
    """A completed scan of every account.

    TestClient runs background tasks before returning, so the scan is done here.
    """
    return client.post("/api/scans").json()["id"]


def all_findings(client, scan_id, **params):
    return client.get(f"/api/scans/{scan_id}/findings", params={"page_size": 100, **params}).json()


# --- health and catalog -------------------------------------------------------


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_checks_catalog(client):
    checks = client.get("/api/checks").json()
    assert len(checks) == 10
    s3 = next(c for c in checks if c["id"] == "AWS-S3-01")
    assert s3 == {
        "id": "AWS-S3-01",
        "title": "S3 bucket blocks public access",
        "severity": "HIGH",
        "provider": "aws",
        "collection": "s3_buckets",
        "resource_id_field": "name",
    }


# --- starting scans -----------------------------------------------------------


def test_start_scan_returns_202_running_then_completes(client):
    response = client.post("/api/scans")
    assert response.status_code == 202
    started = response.json()
    assert started["status"] == "RUNNING"
    assert started["finished_at"] is None
    assert started["score"] is None

    scan = client.get(f"/api/scans/{started['id']}").json()
    assert scan["status"] == "COMPLETED"
    assert scan["finished_at"] is not None
    assert len(scan["account_ids"]) == 4  # "all accounts" resolved when the scan ran


def test_scan_detail_matches_acceptance_numbers(client, scan_id):
    scan = client.get(f"/api/scans/{scan_id}").json()
    assert scan["counts"] == {"PASS": 27, "FAIL": 18, "CANNOT_SCAN": 4}
    assert scan["score"] == 60.0
    assert scan["fail_by_severity"] == {"CRITICAL": 7, "HIGH": 8, "MEDIUM": 2, "LOW": 1}
    scores = {a["account_id"]: a["score"] for a in scan["accounts"]}
    assert scores == {"123456789012": 58.3, "210987654321": 66.7, AZURE: 57.1, GCP: 63.6}
    dev = next(a for a in scan["accounts"] if a["account_id"] == "210987654321")
    assert dev == {
        "account_id": "210987654321",
        "provider": "aws",
        "score": 66.7,
        "counts": {"PASS": 2, "FAIL": 1, "CANNOT_SCAN": 4},
    }


def test_start_scan_with_selected_accounts(client):
    response = client.post("/api/scans", json={"account_ids": [AZURE, AZURE]})
    assert response.status_code == 202
    assert response.json()["account_ids"] == [AZURE]  # duplicates dropped
    scan = client.get(f"/api/scans/{response.json()['id']}").json()
    assert [a["account_id"] for a in scan["accounts"]] == [AZURE]
    assert scan["counts"] == {"PASS": 4, "FAIL": 3, "CANNOT_SCAN": 0}


def test_start_scan_with_empty_object_scans_everything(client):
    response = client.post("/api/scans", json={})
    assert response.status_code == 202
    assert len(client.get(f"/api/scans/{response.json()['id']}").json()["account_ids"]) == 4


def test_empty_account_list_is_422(client):
    response = client.post("/api/scans", json={"account_ids": []})
    assert response.status_code == 422
    assert client.get("/api/scans").json() == []  # nothing was created


def test_unknown_account_is_422(client):
    response = client.post("/api/scans", json={"account_ids": [AZURE, "999999999999"]})
    assert response.status_code == 422
    assert "999999999999" in response.json()["detail"]
    assert client.get("/api/scans").json() == []


def test_malformed_body_is_422(client):
    assert client.post("/api/scans", json={"account_ids": "all"}).status_code == 422


def test_unreadable_snapshot_marks_scan_failed(client, monkeypatch, tmp_path):
    monkeypatch.setenv("INVENTORY_PATH", str(tmp_path / "missing.json"))
    response = client.post("/api/scans")
    assert response.status_code == 202
    scan = client.get(f"/api/scans/{response.json()['id']}").json()
    assert scan["status"] == "FAILED"
    assert "FileNotFoundError" in scan["error"]
    assert scan["score"] is None


# --- reading scans ------------------------------------------------------------


def test_list_scans_newest_first_with_score_and_counts(client):
    first = client.post("/api/scans").json()["id"]
    second = client.post("/api/scans", json={"account_ids": [GCP]}).json()["id"]
    scans = client.get("/api/scans").json()
    assert [s["id"] for s in scans] == [second, first]
    assert scans[0]["counts"] == {"PASS": 7, "FAIL": 4, "CANNOT_SCAN": 0}
    assert scans[0]["score"] == 63.6
    assert scans[1]["score"] == 60.0
    assert set(scans[1]) >= {"id", "status", "started_at", "finished_at", "account_ids"}


def test_unknown_scan_is_404(client):
    assert client.get("/api/scans/999").status_code == 404
    assert client.get("/api/scans/999/findings").status_code == 404


def test_scans_survive_a_restart(client, scan_id):
    with TestClient(app) as restarted:  # startup runs again on the same DB file
        assert restarted.get(f"/api/scans/{scan_id}").json()["counts"]["FAIL"] == 18


def test_scan_left_running_by_a_restart_is_marked_failed(client):
    stuck_id = db.create_scan(None)
    with TestClient(app) as restarted:
        scan = restarted.get(f"/api/scans/{stuck_id}").json()
    assert scan["status"] == "FAILED"
    assert "restart" in scan["error"]


# --- findings: pagination -----------------------------------------------------


def test_findings_default_pagination(client, scan_id):
    page = client.get(f"/api/scans/{scan_id}/findings").json()
    assert (page["total"], page["page"], page["page_size"]) == (49, 1, 25)
    assert len(page["items"]) == 25
    assert set(page["items"][0]) == {
        "id",
        "scan_id",
        "check_id",
        "title",
        "provider",
        "account_id",
        "region",
        "resource_id",
        "status",
        "severity",
        "details",
    }


def test_findings_pages_cover_everything_once(client, scan_id):
    url = f"/api/scans/{scan_id}/findings"
    page1 = client.get(url, params={"page": 1, "page_size": 25}).json()["items"]
    page2 = client.get(url, params={"page": 2, "page_size": 25}).json()["items"]
    page3 = client.get(url, params={"page": 3, "page_size": 25}).json()["items"]
    assert (len(page1), len(page2), page3) == (25, 24, [])
    everything = all_findings(client, scan_id)["items"]
    assert [f["id"] for f in page1 + page2] == [f["id"] for f in everything]


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"page": "x"}]
)
def test_findings_bad_pagination_is_422(client, scan_id, params):
    assert client.get(f"/api/scans/{scan_id}/findings", params=params).status_code == 422


def test_findings_max_page_size_is_100(client, scan_id):
    page = client.get(f"/api/scans/{scan_id}/findings", params={"page_size": 100}).json()
    assert page["page_size"] == 100
    assert len(page["items"]) == 49


# --- findings: ordering -------------------------------------------------------


def test_findings_exact_order(client, scan_id):
    items = all_findings(client, scan_id)["items"]

    def key(f):
        return (
            STATUS_RANK[f["status"]],
            SEVERITY_RANK[f["severity"]],
            f["check_id"],
            f["resource_id"] or "",
        )

    assert [key(f) for f in items] == sorted(key(f) for f in items)
    # Spot-check the boundaries of the order.
    first, last = items[0], items[-1]
    assert (first["status"], first["severity"], first["check_id"], first["resource_id"]) == (
        "FAIL",
        "CRITICAL",
        "AWS-EC2-01",
        "sg-0a1b2c3d4e5f60002",
    )
    assert (last["status"], last["severity"], last["check_id"]) == ("PASS", "LOW", "GCP-GCS-02")
    statuses = [f["status"] for f in items]
    assert statuses == ["FAIL"] * 18 + ["CANNOT_SCAN"] * 4 + ["PASS"] * 27


def test_cannot_scan_order_within_group(client, scan_id):
    items = all_findings(client, scan_id, status="CANNOT_SCAN")["items"]
    assert [(f["check_id"], f["resource_id"]) for f in items] == [
        ("AWS-EC2-01", "sg-0b1c2d3e4f5a60002"),  # CRITICAL first
        ("AWS-IAM-01", None),  # then HIGH, by check ID
        ("AWS-RDS-01", None),
        ("AWS-IAM-02", None),  # then MEDIUM
    ]


# --- findings: filters --------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected_total"),
    [
        ({"status": "FAIL"}, 18),
        ({"status": "fail"}, 18),
        ({"status": "cannot_scan"}, 4),
        ({"severity": "critical"}, 18),
        ({"severity": "Low"}, 3),
        ({"provider": "AZURE"}, 7),
        ({"account_id": "EXAMPLE-CORP-GCP"}, 11),
        ({"account_id": "210987654321"}, 7),
        ({"check_id": "aws-iam-02"}, 7),
        ({"status": "fail", "provider": "gcp"}, 4),
        ({"status": "fail", "severity": "critical", "account_id": "123456789012"}, 4),
        ({"status": "unknown"}, 0),
    ],
)
def test_findings_filters(client, scan_id, params, expected_total):
    page = all_findings(client, scan_id, **params)
    assert page["total"] == expected_total
    assert len(page["items"]) == expected_total
    for name, value in params.items():
        assert all(item[name].lower() == value.lower() for item in page["items"])


def test_filter_total_is_independent_of_page(client, scan_id):
    url = f"/api/scans/{scan_id}/findings"
    page = client.get(url, params={"status": "pass", "page_size": 10, "page": 2}).json()
    assert page["total"] == 27
    assert len(page["items"]) == 10


def test_untrusted_strings_are_returned_verbatim(client, scan_id):
    items = all_findings(client, scan_id, check_id="GCP-VPC-01", status="FAIL")["items"]
    assert "<img src=x onerror=alert('untrusted-input')>" in items[0]["details"]


def test_filter_values_are_not_sql(client, scan_id):
    page = all_findings(client, scan_id, status="FAIL' OR '1'='1")
    assert page["total"] == 0
