"""Fail-closed configuration for explicitly provisioned, isolated QA fixtures.

These helpers never provision accounts, infer credentials, or contact production.
Set AURORA_QA_ISOLATED=1 only for a disposable local test deployment.
"""
import os
from urllib.parse import urlsplit


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required isolated QA configuration is missing: {name}")
    return value


def isolated_url(name):
    if required_env("AURORA_QA_ISOLATED") != "1":
        raise RuntimeError("QA requires explicit isolated deployment acknowledgement")
    value = required_env(name)
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise RuntimeError(f"{name} must be a credential-free loopback URL")
    return value.rstrip("/")


def credentials(prefix="AURORA_QA"):
    return {"email": required_env(f"{prefix}_EMAIL"),
            "password": required_env(f"{prefix}_PASSWORD")}


def require_check(results, name, passed):
    results[name] = bool(passed)
    if not passed:
        raise AssertionError(f"QA check failed: {name}")
