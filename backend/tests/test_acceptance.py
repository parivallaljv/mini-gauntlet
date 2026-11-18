"""Golden test: the exact status of every finding for data/inventory.json.

Totals can hide two mistakes that cancel out; this pins each of the 49 findings.
"""

import pytest

from app.scanner.engine import load_inventory, run_scan, scan_account
from app.scanner.models import Status
from app.scanner.registry import CHECKS

from .conftest import INVENTORY_PATH, SNAPSHOT_TIME

P, F, C = Status.PASS, Status.FAIL, Status.CANNOT_SCAN
PROD, DEV = "123456789012", "210987654321"
AZURE, GCP = "8f14e45f-ceea-4e7a-9d3b-2f6c1a0b7d21", "example-corp-gcp"

EXPECTED = {
    # prod
    (PROD, "AWS-S3-01", "example-corp-web-assets"): P,
    (PROD, "AWS-S3-01", "example-corp-public-downloads"): F,  # two flags off
    (PROD, "AWS-S3-01", "example-corp-logs"): F,  # public_access_block is null
    (PROD, "AWS-EC2-01", "sg-0a1b2c3d4e5f60001"): P,  # 443 only
    (PROD, "AWS-EC2-01", "sg-0a1b2c3d4e5f60002"): F,  # 22 from 0.0.0.0/0
    (PROD, "AWS-EC2-01", "sg-0a1b2c3d4e5f60003"): F,  # 3000-3500 includes 3389
    (PROD, "AWS-EC2-01", "sg-0a1b2c3d4e5f60004"): F,  # 22 from ::/0
    (PROD, "AWS-EC2-01", "sg-0a1b2c3d4e5f60005"): P,  # office CIDR
    (PROD, "AWS-EC2-01", "sg-0a1b2c3d4e5f60006"): F,  # protocol -1
    (PROD, "AWS-EC2-01", "sg-0a1b2c3d4e5f60007"): P,  # UDP 53
    (PROD, "AWS-IAM-01", "alice"): P,
    (PROD, "AWS-IAM-01", "bob"): F,  # console, no MFA
    (PROD, "AWS-IAM-01", "ci-deployer"): P,
    (PROD, "AWS-IAM-01", "reporting-bot"): P,
    (PROD, "AWS-IAM-01", "legacy-etl"): P,
    (PROD, "AWS-IAM-01", "former-contractor"): P,
    (PROD, "AWS-IAM-02", "alice"): P,
    (PROD, "AWS-IAM-02", "bob"): P,  # no keys
    (PROD, "AWS-IAM-02", "ci-deployer"): P,  # exactly 90 days
    (PROD, "AWS-IAM-02", "reporting-bot"): F,  # 91 days
    (PROD, "AWS-IAM-02", "legacy-etl"): F,  # active key 320 days
    (PROD, "AWS-IAM-02", "former-contractor"): P,  # only an inactive key
    (PROD, "AWS-RDS-01", "orders-db"): P,
    (PROD, "AWS-RDS-01", "analytics-replica"): F,
    # dev
    (DEV, "AWS-S3-01", "example-corp-dev-artifacts"): P,
    (DEV, "AWS-S3-01", "example-corp-dev-scratch"): F,
    (DEV, "AWS-EC2-01", "sg-0b1c2d3e4f5a60001"): P,
    (DEV, "AWS-EC2-01", "sg-0b1c2d3e4f5a60002"): C,  # from_port "twenty-two"
    (DEV, "AWS-IAM-01", None): C,  # AccessDenied
    (DEV, "AWS-IAM-02", None): C,  # AccessDenied
    (DEV, "AWS-RDS-01", None): C,  # UnauthorizedOperation
    # azure
    (AZURE, "AZ-STG-01", "examplecorpdata"): P,
    (AZURE, "AZ-STG-01", "examplecorppublic"): F,
    (AZURE, "AZ-STG-01", "examplecorpbackup"): P,
    (AZURE, "AZ-NSG-01", "nsg-web"): P,
    (AZURE, "AZ-NSG-01", "nsg-jumpbox"): F,  # 22 from *
    (AZURE, "AZ-NSG-01", "nsg-mgmt"): F,  # 3380-3400 includes 3389
    (AZURE, "AZ-NSG-01", "nsg-locked"): P,  # Deny + Outbound
    # gcp
    (GCP, "GCP-GCS-01", "example-corp-public-site"): F,  # allUsers
    (GCP, "GCP-GCS-01", "example-corp-ml-data"): P,
    (GCP, "GCP-GCS-01", "example-corp-partner-share"): F,  # allAuthenticatedUsers
    (GCP, "GCP-GCS-02", "example-corp-public-site"): P,
    (GCP, "GCP-GCS-02", "example-corp-ml-data"): F,
    (GCP, "GCP-GCS-02", "example-corp-partner-share"): P,
    (GCP, "GCP-VPC-01", "allow-ssh-from-iap"): P,
    (GCP, "GCP-VPC-01", "allow-rdp-anywhere"): F,
    (GCP, "GCP-VPC-01", "allow-all-disabled"): P,  # disabled
    (GCP, "GCP-VPC-01", "allow-app-ports"): P,  # 8000-9000
    (GCP, "GCP-VPC-01", "allow-ssh-egress"): P,  # EGRESS
}


def test_every_finding_has_the_expected_status():
    inventory = load_inventory(str(INVENTORY_PATH))
    for account in inventory["accounts"]:  # in-memory copy only; skip the latency
        account["simulated_latency_ms"] = 0
    actual = {(f.account_id, f.check_id, f.resource_id): f.status for f in run_scan(inventory)}
    assert actual == EXPECTED


@pytest.mark.parametrize("chk", CHECKS, ids=lambda c: c.id)
def test_every_check_reports_an_unreadable_collection(chk):
    account = {
        "provider": chk.provider,
        "account_id": "acct",
        "errors": {chk.collection: "AccessDenied"},
        "resources": {},
    }
    findings = [f for f in scan_account(account, SNAPSHOT_TIME) if f.check_id == chk.id]
    assert len(findings) == 1
    assert findings[0].status == Status.CANNOT_SCAN
    assert findings[0].resource_id is None
    assert "AccessDenied" in findings[0].details
