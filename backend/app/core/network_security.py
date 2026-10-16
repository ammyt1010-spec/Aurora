"""Network security helpers to detect proxy headers, tunnels, and loopback boundaries."""
from __future__ import annotations

import ipaddress
from fastapi import Request

LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "testclient", "test"}
BLOCKED_TUNNEL_HEADERS = {
    "cf-connecting-ip",
    "cf-ray",
    "cf-visitor",
    "cf-ipcountry",
    "true-client-ip",
    "x-envoy-external-address",
    "x-azure-clientip",
    "x-amzn-trace-id",
}


def is_loopback_ip(ip_str: str) -> bool:
    try:
        # Strip port if present
        clean_ip = ip_str.strip()
        if ":" in clean_ip and not clean_ip.startswith("[") and clean_ip.count(":") == 1:
            clean_ip = clean_ip.split(":")[0]
        ip = ipaddress.ip_address(clean_ip)
        return ip.is_loopback
    except ValueError:
        return clean_ip.lower() in LOOPBACK_HOSTNAMES


def is_direct_local_request(request: Request) -> bool:
    """Return True only if the request originated directly from the loopback interface without external proxies or public tunnels."""
    # 1. Client host must exist and be loopback
    client_host = request.client.host if request.client else ""
    if not is_loopback_ip(client_host):
        return False

    headers = request.headers

    # 2. Check for public tunnel / CDN provider headers
    for hdr in BLOCKED_TUNNEL_HEADERS:
        if hdr in headers:
            return False

    # 3. Host and X-Forwarded-Host must be loopback
    host_header = headers.get("host", "").split(":")[0].strip().lower()
    if host_header and host_header not in LOOPBACK_HOSTNAMES:
        return False

    fwd_host = headers.get("x-forwarded-host", "").split(":")[0].strip().lower()
    if fwd_host and fwd_host not in LOOPBACK_HOSTNAMES:
        return False

    # 4. Check X-Forwarded-For chain: every single IP in the chain must be loopback
    xff = headers.get("x-forwarded-for")
    if xff:
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        for ip in ips:
            if not is_loopback_ip(ip):
                return False

    # 5. Check X-Real-IP
    real_ip = headers.get("x-real-ip")
    if real_ip and not is_loopback_ip(real_ip):
        return False

    # 6. Check standard RFC 7239 Forwarded header
    forwarded = headers.get("forwarded")
    if forwarded:
        lower_fwd = forwarded.lower()
        if "for=" in lower_fwd:
            for part in lower_fwd.split(";"):
                part = part.strip()
                if part.startswith("for="):
                    val = part[4:].strip('"').strip('[]')
                    if not is_loopback_ip(val):
                        return False

    # 7. Reverse proxy TLS termination indicating external access
    if headers.get("x-forwarded-proto", "").lower() == "https":
        return False

    return True
