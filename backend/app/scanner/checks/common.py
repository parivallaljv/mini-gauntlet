"""Small helpers shared by the checks.

Every value read from the snapshot is untrusted: helpers validate types and raise
CannotScan (never a generic error) when a field can't be evaluated.
"""

from datetime import datetime, timezone
from typing import Any

from ..models import CannotScan

ALL_PORTS = (0, 65535)
# The ports the "SSH or RDP" checks care about.
ADMIN_PORTS = {22: "SSH", 3389: "RDP"}
# CIDRs that mean "the whole internet" (IPv4 and IPv6).
INTERNET_CIDRS = {"0.0.0.0/0", "::/0"}


def require_bool(resource: dict[str, Any], field: str) -> bool:
    value = resource.get(field)
    if not isinstance(value, bool):
        raise CannotScan(f"{field} is {value!r}, expected true or false")
    return value


def require_list(resource: dict[str, Any], field: str) -> list[Any]:
    value = resource.get(field)
    if not isinstance(value, list):
        raise CannotScan(f"{field} is {value!r}, expected a list")
    return value


def parse_port(value: Any) -> int:
    """Turn 22 or "22" into 22. Anything else (e.g. "twenty-two") can't be scanned."""
    # bool is a subclass of int in Python, so reject it explicitly.
    if isinstance(value, int) and not isinstance(value, bool):
        port = value
    elif isinstance(value, str) and value.strip().isdigit():
        port = int(value)
    else:
        raise CannotScan(f"port {value!r} is not a number")
    if not 0 <= port <= 65535:
        raise CannotScan(f"port {port} is out of range")
    return port


def parse_port_range(text: Any) -> tuple[int, int]:
    """Parse "22", "3380-3400" or "*" (all ports) into an inclusive (low, high) pair."""
    if not isinstance(text, str):
        raise CannotScan(f"port range {text!r} is not a string")
    text = text.strip()
    if text == "*":
        return ALL_PORTS
    low, sep, high = text.partition("-")
    if not sep:
        port = parse_port(low)
        return port, port
    low_port, high_port = parse_port(low), parse_port(high)
    if low_port > high_port:
        raise CannotScan(f"port range {text!r} is reversed")
    return low_port, high_port


def exposed_admin_ports(low: int, high: int) -> list[str]:
    """Names of the admin ports inside low..high, e.g. ["RDP (3389)"]."""
    return [f"{name} ({port})" for port, name in ADMIN_PORTS.items() if low <= port <= high]


def describe_ports(low: int, high: int) -> str:
    if (low, high) == ALL_PORTS:
        return "all ports"
    if low == high:
        return f"port {low}"
    return f"ports {low}-{high}"


def parse_time(value: Any) -> datetime:
    """Parse an ISO 8601 timestamp. A trailing "Z" is accepted; naive times are UTC."""
    if not isinstance(value, str):
        raise CannotScan(f"timestamp {value!r} is not a string")
    try:
        # fromisoformat only accepts "Z" from Python 3.11, so normalise it.
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CannotScan(f"timestamp {value!r} is not ISO 8601") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
