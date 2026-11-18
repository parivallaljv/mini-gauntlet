import pytest

from app.scanner.checks.aws import (
    access_keys_rotated,
    console_users_have_mfa,
    rds_not_public,
    s3_blocks_public_access,
    security_group_admin_ports,
)

from .conftest import assert_cannot_scan, assert_fail, assert_pass

ALL_ON = {
    "block_public_acls": True,
    "ignore_public_acls": True,
    "block_public_policy": True,
    "restrict_public_buckets": True,
}


# --- AWS-S3-01 ---------------------------------------------------------------


def test_s3_pass_when_all_four_flags_on():
    assert_pass(s3_blocks_public_access, {"name": "b", "public_access_block": ALL_ON})


def test_s3_fail_names_the_disabled_flags():
    block = {**ALL_ON, "block_public_policy": False, "restrict_public_buckets": False}
    details = assert_fail(
        s3_blocks_public_access,
        {"public_access_block": block},
        "block_public_policy",
        "restrict_public_buckets",
    )
    assert "block_public_acls" not in details


def test_s3_null_block_fails():
    assert_fail(s3_blocks_public_access, {"public_access_block": None}, "No public access block")


def test_s3_missing_flag_counts_as_off():
    block = {k: v for k, v in ALL_ON.items() if k != "ignore_public_acls"}
    assert_fail(s3_blocks_public_access, {"public_access_block": block}, "ignore_public_acls")


def test_s3_cannot_scan_non_bool_flag():
    block = {**ALL_ON, "block_public_acls": "yes"}
    assert_cannot_scan(s3_blocks_public_access, {"public_access_block": block}, "block_public_acls")


def test_s3_cannot_scan_block_that_is_not_an_object():
    assert_cannot_scan(s3_blocks_public_access, {"public_access_block": "on"})


# --- AWS-EC2-01 --------------------------------------------------------------


def sg(*rules):
    return {"group_id": "sg-1", "ingress": list(rules)}


def rule(protocol="tcp", from_port=22, to_port=22, cidrs=("0.0.0.0/0",)):
    return {"protocol": protocol, "from_port": from_port, "to_port": to_port, "cidrs": list(cidrs)}


def test_ec2_ssh_from_internet_fails_with_port_and_source():
    assert_fail(security_group_admin_ports, sg(rule()), "port 22", "0.0.0.0/0", "SSH")


def test_ec2_rdp_from_internet_fails():
    assert_fail(security_group_admin_ports, sg(rule(from_port=3389, to_port=3389)), "RDP (3389)")


def test_ec2_ipv6_any_fails():
    assert_fail(security_group_admin_ports, sg(rule(cidrs=["::/0"])), "::/0")


@pytest.mark.parametrize(
    ("low", "high", "expected"),
    [
        (3000, 3500, "ports 3000-3500"),  # range containing 3389
        (20, 25, "ports 20-25"),  # range containing 22
        (3390, 3500, None),  # range just above 3389
        (23, 3388, None),  # range strictly between 22 and 3389
        (0, 65535, "all ports"),  # every port
    ],
)
def test_ec2_port_ranges(low, high, expected):
    resource = sg(rule(from_port=low, to_port=high))
    if expected:
        assert_fail(security_group_admin_ports, resource, expected)
    else:
        assert_pass(security_group_admin_ports, resource)


def test_ec2_protocol_minus_one_means_all_ports():
    resource = sg(rule(protocol="-1", from_port=None, to_port=None))
    assert_fail(security_group_admin_ports, resource, "all ports", "SSH (22)", "RDP (3389)")


def test_ec2_private_source_passes():
    assert_pass(security_group_admin_ports, sg(rule(cidrs=["203.0.113.0/24", "10.0.0.0/8"])))


def test_ec2_https_from_internet_passes():
    assert_pass(security_group_admin_ports, sg(rule(from_port=443, to_port=443)))


def test_ec2_udp_is_ignored():
    assert_pass(security_group_admin_ports, sg(rule(protocol="udp", from_port=0, to_port=65535)))


def test_ec2_no_ingress_rules_passes():
    assert_pass(security_group_admin_ports, sg())


def test_ec2_numeric_string_port_is_accepted():
    assert_fail(security_group_admin_ports, sg(rule(from_port="22", to_port="22")), "SSH")


@pytest.mark.parametrize("bad_port", ["twenty-two", None, True, -1, 70000, 22.5])
def test_ec2_bad_port_cannot_scan(bad_port):
    assert_cannot_scan(security_group_admin_ports, sg(rule(from_port=bad_port)), "port")


def test_ec2_missing_ingress_cannot_scan():
    assert_cannot_scan(security_group_admin_ports, {"group_id": "sg-1"}, "ingress")


# --- AWS-IAM-01 --------------------------------------------------------------


def test_iam_mfa_pass_with_console_and_mfa():
    assert_pass(console_users_have_mfa, {"console_access": True, "mfa_enabled": True})


def test_iam_mfa_fail_console_without_mfa():
    assert_fail(console_users_have_mfa, {"console_access": True, "mfa_enabled": False}, "MFA")


def test_iam_mfa_no_console_passes_even_without_mfa():
    assert_pass(console_users_have_mfa, {"console_access": False, "mfa_enabled": False})


def test_iam_mfa_cannot_scan_missing_field():
    assert_cannot_scan(console_users_have_mfa, {"console_access": True}, "mfa_enabled")


# --- AWS-IAM-02 --------------------------------------------------------------


def user_with_keys(*keys):
    return {"user_name": "u", "access_keys": list(keys)}


def key(created_at, status="Active", key_id="k1"):
    return {"key_id": key_id, "status": status, "created_at": created_at}


def test_iam_key_exactly_90_days_old_passes():
    # 2026-07-03 -> 2026-10-01 is exactly 90 days.
    assert_pass(access_keys_rotated, user_with_keys(key("2026-07-03T00:00:00Z")))


def test_iam_key_91_days_old_fails_with_age():
    assert_fail(
        access_keys_rotated,
        user_with_keys(key("2026-07-02T00:00:00Z", key_id="example-key-0003")),
        "example-key-0003",
        "91 days",
    )


def test_iam_key_one_second_over_90_days_fails():
    assert_fail(access_keys_rotated, user_with_keys(key("2026-07-02T23:59:59Z")))


def test_iam_inactive_old_key_is_ignored():
    assert_pass(access_keys_rotated, user_with_keys(key("2020-01-01T00:00:00Z", status="Inactive")))


def test_iam_only_active_old_key_is_reported():
    details = assert_fail(
        access_keys_rotated,
        user_with_keys(
            key("2025-11-15T00:00:00Z", key_id="active-old"),
            key("2024-01-10T00:00:00Z", status="Inactive", key_id="inactive-old"),
        ),
        "active-old",
    )
    assert "inactive-old" not in details


def test_iam_no_keys_passes():
    assert_pass(access_keys_rotated, user_with_keys())


def test_iam_bad_date_cannot_scan():
    assert_cannot_scan(access_keys_rotated, user_with_keys(key("last tuesday")), "ISO 8601")


def test_iam_key_without_status_cannot_scan():
    bad_key = {"key_id": "k", "created_at": "2026-09-01T00:00:00Z"}
    assert_cannot_scan(access_keys_rotated, user_with_keys(bad_key), "status")


# --- AWS-RDS-01 --------------------------------------------------------------


def test_rds_private_passes():
    assert_pass(rds_not_public, {"publicly_accessible": False})


def test_rds_public_fails():
    assert_fail(rds_not_public, {"publicly_accessible": True}, "publicly accessible")


def test_rds_missing_field_cannot_scan():
    assert_cannot_scan(rds_not_public, {}, "publicly_accessible")
