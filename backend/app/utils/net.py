"""
Network safety helpers.

Guards against SSRF by validating that a user-supplied URL points to a
public host over HTTPS before the server makes any request to it.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

# Extra hosts to block outright (cloud metadata endpoints, wildcard address).
_BLOCKED_LITERALS = {
    "169.254.169.254",  # AWS/GCP/Azure metadata (IPv4)
    "0.0.0.0",
    "fd00:ec2::254",  # AWS metadata (IPv6)
}


def _is_blocked_ip(ip_str: str) -> bool:
    """Return True if the IP must not be reached from the server."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Unparseable address -> treat as unsafe
        return True

    # IPv6 may wrap an IPv4 address (e.g. ::ffff:169.254.169.254)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    if str(ip) in _BLOCKED_LITERALS:
        return True

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> None:
    """
    Validate that ``url`` is safe for the server to request.

    Requires an ``https`` scheme and a hostname that resolves only to public
    IP addresses. Rejects private/loopback/link-local/reserved/multicast and
    cloud-metadata targets (IPv4 and IPv6) to prevent SSRF.

    Raises ``HTTPException(400, "Invalid URL")`` on any failure.
    """
    if not url:
        raise HTTPException(status_code=400, detail="Invalid URL")

    try:
        parsed = urlparse(url)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if parsed.scheme not in ("https",):
        raise HTTPException(status_code=400, detail="Invalid URL")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid URL")

    # Resolve every address the hostname maps to and reject if any is unsafe.
    # A literal IP simply resolves to itself, so this also covers IP URLs.
    try:
        addr_infos = socket.getaddrinfo(
            hostname,
            parsed.port or 443,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if not addr_infos:
        raise HTTPException(status_code=400, detail="Invalid URL")

    for info in addr_infos:
        ip_str = info[4][0]
        if _is_blocked_ip(ip_str):
            raise HTTPException(status_code=400, detail="Invalid URL")
