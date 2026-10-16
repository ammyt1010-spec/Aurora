"""Network security helpers to detect proxy headers, tunnels, and loopback boundaries."""
from __future__ import annotations

import ipaddress
from fastapi import Request

LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "testclient", "test"}
BLOCKED_PROXY_HEADERS = {
    "cf-connecting-ip",
    "cf-ray",
    "cf-visitor",
    "cf-ipcountry",
    "cf-worker",
    "true-client-ip",
    "x-envoy-external-address",
    "x-azure-clientip",
    "x-amzn-trace-id",
    "via",
    "forwarded",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-forwarded-server",
    "x-forwarded-by",
    "x-cluster-client-ip",
}


def is_loopback_ip(ip_str: str) -> bool:
    if not ip_str:
        return False
    clean_ip = ip_str.strip().lower()
    # Explicitly reject INADDR_ANY (0.0.0.0, ::) - NEVER a loopback address!
    if clean_ip in ("0.0.0.0", "::", "0:0:0:0:0:0:0:0"):
        return False
    # Strip port if present e.g. "127.0.0.1:8000"
    if ":" in clean_ip and not clean_ip.startswith("[") and clean_ip.count(":") == 1:
        clean_ip = clean_ip.split(":")[0]
    if clean_ip in ("0.0.0.0", "::"):
        return False
    try:
        ip = ipaddress.ip_address(clean_ip)
        return ip.is_loopback
    except ValueError:
        return clean_ip in LOOPBACK_HOSTNAMES


def is_direct_local_request(request: Request) -> bool:
    """Return True only if the request originated directly from the loopback interface

    without external proxies, public tunnels, or spoofed headers.
    """
    # 1. Client host must exist and be strictly loopback (never 0.0.0.0 or empty)
    client_host = request.client.host if request.client else ""
    if not client_host or not is_loopback_ip(client_host):
        return False

    headers = request.headers

    # 2. Check for public tunnel / CDN provider / proxy indicator headers
    for hdr in BLOCKED_PROXY_HEADERS:
        val = headers.get(hdr)
        if val:
            return False

    # 3. Host and X-Forwarded-Host must be strictly loopback (never 0.0.0.0, never external)
    host_header = headers.get("host", "").split(":")[0].strip().lower()
    if not host_header or host_header not in LOOPBACK_HOSTNAMES or host_header == "0.0.0.0":
        return False

    fwd_host = headers.get("x-forwarded-host", "").split(":")[0].strip().lower()
    if fwd_host and (fwd_host not in LOOPBACK_HOSTNAMES or fwd_host == "0.0.0.0"):
        return False

    # 4. Check X-Forwarded-For chain: every single IP in the chain must be strictly loopback
    xff = headers.get("x-forwarded-for")
    if xff:
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        for ip in ips:
            if not is_loopback_ip(ip):
                return False

    # 5. Check X-Real-IP and X-Client-IP
    for real_hdr in ("x-real-ip", "x-client-ip"):
        real_ip = headers.get(real_hdr)
        if real_ip and not is_loopback_ip(real_ip):
            return False

    # 6. Check Origin header: if present, origin host must strictly be loopback
    origin = headers.get("origin")
    if origin:
        clean_origin = (
            origin.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip().lower()
        )
        if not clean_origin or clean_origin not in LOOPBACK_HOSTNAMES or clean_origin == "0.0.0.0":
            return False

    # 7. Check Referer header: if present, referer host must strictly be loopback
    referer = headers.get("referer")
    if referer:
        clean_ref = (
            referer.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip().lower()
        )
        if not clean_ref or clean_ref not in LOOPBACK_HOSTNAMES or clean_ref == "0.0.0.0":
            return False

    # 8. Reverse proxy TLS termination indicating external access
    if headers.get("x-forwarded-proto", "").lower() == "https":
        return False

    return True
