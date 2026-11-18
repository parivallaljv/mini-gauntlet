import pytest

from app.scanner.checks.gcp import bucket_not_public, bucket_uniform_access, firewall_admin_ports

from .conftest import assert_cannot_scan, assert_fail, assert_pass

# --- GCP-GCS-01 --------------------------------------------------------------


def bucket(*members, role="roles/storage.objectViewer"):
    return {"name": "b", "iam_bindings": [{"role": role, "members": list(members)}]}


def test_bucket_private_passes():
    assert_pass(bucket_not_public, bucket("group:data-eng@example.com"))


def test_bucket_all_users_fails_with_role():
    assert_fail(bucket_not_public, bucket("allUsers"), "allUsers", "roles/storage.objectViewer")


def test_bucket_all_authenticated_users_counts_as_public():
    assert_fail(
        bucket_not_public, bucket("allAuthenticatedUsers", "user:a@example.com"), "allAuthenticated"
    )


def test_bucket_no_bindings_passes():
    assert_pass(bucket_not_public, {"iam_bindings": []})


def test_bucket_missing_bindings_cannot_scan():
    assert_cannot_scan(bucket_not_public, {"name": "b"}, "iam_bindings")


# --- GCP-GCS-02 --------------------------------------------------------------


def test_uniform_access_on_passes():
    assert_pass(bucket_uniform_access, {"uniform_bucket_level_access": True})


def test_uniform_access_off_fails():
    assert_fail(bucket_uniform_access, {"uniform_bucket_level_access": False}, "Uniform")


def test_uniform_access_missing_cannot_scan():
    assert_cannot_scan(bucket_uniform_access, {}, "uniform_bucket_level_access")


# --- GCP-VPC-01 --------------------------------------------------------------


def fw(ports=("22",), protocol="tcp", sources=("0.0.0.0/0",), **extra):
    allowed = {"IPProtocol": protocol}
    if ports is not None:
        allowed["ports"] = list(ports)
    return {
        "name": "fw",
        "direction": "INGRESS",
        "disabled": False,
        "source_ranges": list(sources),
        "allowed": [allowed],
        **extra,
    }


def test_firewall_ssh_from_internet_fails():
    assert_fail(firewall_admin_ports, fw(), "port 22", "0.0.0.0/0", "SSH")


def test_firewall_ipv6_any_fails():
    assert_fail(firewall_admin_ports, fw(sources=["::/0"]), "::/0")


@pytest.mark.parametrize(
    ("spec", "fails"),
    [("3389", True), ("3000-4000", True), ("8000-9000", False), ("443", False)],
)
def test_firewall_port_ranges(spec, fails):
    if fails:
        assert_fail(firewall_admin_ports, fw(ports=[spec]))
    else:
        assert_pass(firewall_admin_ports, fw(ports=[spec]))


def test_firewall_protocol_all_means_every_port():
    assert_fail(firewall_admin_ports, fw(ports=None, protocol="all"), "all ports")


def test_firewall_tcp_without_ports_means_every_port():
    assert_fail(firewall_admin_ports, fw(ports=None), "all ports")


def test_firewall_disabled_rule_never_fails():
    assert_pass(firewall_admin_ports, fw(ports=None, protocol="all", disabled=True))


def test_firewall_egress_rule_never_fails():
    rule = fw(direction="EGRESS")
    rule["destination_ranges"] = rule.pop("source_ranges")
    assert_pass(firewall_admin_ports, rule)


def test_firewall_private_source_passes():
    assert_pass(firewall_admin_ports, fw(sources=["35.235.240.0/20"]))


def test_firewall_udp_is_ignored():
    assert_pass(firewall_admin_ports, fw(protocol="udp", ports=["3389"]))


def test_firewall_details_include_untrusted_description_verbatim():
    payload = "<img src=x onerror=alert('untrusted-input')> temporary rule"
    details = assert_fail(firewall_admin_ports, fw(ports=["3389"], description=payload))
    assert payload in details  # stored as-is; the dashboard renders it as text


def test_firewall_non_numeric_port_cannot_scan():
    assert_cannot_scan(firewall_admin_ports, fw(ports=["ssh"]), "not a number")


def test_firewall_non_bool_disabled_cannot_scan():
    assert_cannot_scan(firewall_admin_ports, fw(disabled="no"), "disabled")
