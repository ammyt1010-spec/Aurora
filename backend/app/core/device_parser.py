"""Privacy-preserving device and network metadata parsing."""
from __future__ import annotations

import re


def parse_device_info(user_agent: str | None) -> dict[str, str]:
    if not user_agent:
        return {
            "device_family": "Unknown",
            "os_family": "Unknown",
            "browser_family": "Unknown",
        }

    ua = user_agent.lower()

    # Detect Device Family
    if "tablet" in ua or "ipad" in ua:
        device_family = "Tablet"
    elif "mobile" in ua or "iphone" in ua or "android" in ua and "mobile" in ua:
        device_family = "Mobile"
    elif "bot" in ua or "crawler" in ua or "spider" in ua:
        device_family = "Bot"
    else:
        device_family = "Desktop"

    # Detect OS Family
    if "windows" in ua:
        os_family = "Windows"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        os_family = "iOS"
    elif "macintosh" in ua or "mac os" in ua:
        os_family = "macOS"
    elif "android" in ua:
        os_family = "Android"
    elif "cros" in ua:
        os_family = "ChromeOS"
    elif "linux" in ua:
        os_family = "Linux"
    else:
        os_family = "Unknown"

    # Detect Browser Family (order matters due to UA token inheritance)
    if "edg/" in ua or "edge/" in ua:
        browser_family = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser_family = "Opera"
    elif "firefox" in ua or "fxios" in ua:
        browser_family = "Firefox"
    elif "chrome" in ua or "crios" in ua:
        browser_family = "Chrome"
    elif "safari" in ua and "chrome" not in ua and "crios" not in ua:
        browser_family = "Safari"
    else:
        browser_family = "Unknown"

    return {
        "device_family": device_family,
        "os_family": os_family,
        "browser_family": browser_family,
    }


def anonymize_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    ip = ip.strip()
    if ip in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return "127.0.0.1"

    # IPv4
    ipv4_match = re.match(r"^(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}$", ip)
    if ipv4_match:
        return f"{ipv4_match.group(1)}.***"

    # IPv6
    if ":" in ip:
        parts = ip.split(":")
        prefix = ":".join(parts[:3])
        return f"{prefix}::***"

    return "Anonymized"
