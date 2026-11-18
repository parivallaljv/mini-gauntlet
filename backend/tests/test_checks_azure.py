import pytest

from app.scanner.checks.azure import nsg_admin_ports, storage_blocks_public_blobs

from .conftest import assert_cannot_scan, assert_fail, assert_pass

# --- AZ-STG-01 ---------------------------------------------------------------


def test_storage_private_passes():
    assert_pass(storage_blocks_public_blobs, {"allow_blob_public_access": False})


def test_storage_public_fails():
    assert_fail(
        storage_blocks_public_blobs, {"allow_blob_public_access": True}, "allow_blob_public_access"
    )


def test_storage_missing_field_cannot_scan():
    assert_cannot_scan(storage_blocks_public_blobs, {"name": "x"}, "allow_blob_public_access")


# --- AZ-NSG-01 ---------------------------------------------------------------


def nsg(*rules):
    return {"name": "nsg", "rules": list(rules)}


def rule(
    name="r",
    direction="Inbound",
    access="Allow",
    protocol="Tcp",
    source="Internet",
    ports="22",
):
    return {
        "name": name,
        "direction": direction,
        "access": access,
        "protocol": protocol,
        "source": source,
        "destination_ports": ports,
    }


@pytest.mark.parametrize("source", ["Internet", "*", "0.0.0.0/0", "::/0", "Any"])
def test_nsg_ssh_from_any_internet_source_fails(source):
    assert_fail(nsg_admin_ports, nsg(rule(name="allow-ssh", source=source)), "allow-ssh", "port 22")


def test_nsg_port_range_containing_rdp_fails():
    assert_fail(nsg_admin_ports, nsg(rule(ports="3380-3400")), "ports 3380-3400", "RDP (3389)")


def test_nsg_port_range_without_admin_ports_passes():
    assert_pass(nsg_admin_ports, nsg(rule(ports="8000-9000")))


def test_nsg_star_ports_and_star_protocol_fail():
    assert_fail(nsg_admin_ports, nsg(rule(protocol="*", ports="*")), "all ports")


def test_nsg_comma_separated_ports():
    assert_fail(nsg_admin_ports, nsg(rule(ports="80,443,3389")), "RDP")


def test_nsg_deny_rule_never_fails():
    assert_pass(nsg_admin_ports, nsg(rule(access="Deny")))


def test_nsg_outbound_rule_never_fails():
    assert_pass(nsg_admin_ports, nsg(rule(direction="Outbound", source="*")))


def test_nsg_udp_is_ignored():
    assert_pass(nsg_admin_ports, nsg(rule(protocol="Udp", ports="*")))


def test_nsg_private_source_passes():
    assert_pass(nsg_admin_ports, nsg(rule(source="10.0.0.0/8")))


def test_nsg_https_from_internet_passes():
    assert_pass(nsg_admin_ports, nsg(rule(ports="443")))


def test_nsg_matching_is_case_insensitive():
    resource = nsg(rule(direction="INBOUND", access="allow", protocol="TCP", source="internet"))
    assert_fail(nsg_admin_ports, resource)


def test_nsg_non_numeric_port_cannot_scan():
    assert_cannot_scan(nsg_admin_ports, nsg(rule(ports="ssh")), "not a number")


def test_nsg_reversed_range_cannot_scan():
    assert_cannot_scan(nsg_admin_ports, nsg(rule(ports="3400-3380")), "reversed")


def test_nsg_missing_rules_cannot_scan():
    assert_cannot_scan(nsg_admin_ports, {"name": "nsg"}, "rules")
