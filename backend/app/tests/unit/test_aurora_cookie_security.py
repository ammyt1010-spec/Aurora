from fastapi import Request, Response
import pytest

from app.core.auth_cookie import add_session_cookies, clear_session_cookies, validate_cookie_csrf
from app.core.exceptions import AuthorizationError


def _request(method, cookie, csrf):
    headers = [(b"cookie", cookie.encode())]
    if csrf is not None:
        headers.append((b"x-csrf-token", csrf.encode()))
    return Request({"type": "http", "method": method, "path": "/api/v1/projects/1",
                    "headers": headers, "query_string": b""})


def test_csrf_enforced_only_for_cookie_unsafe_methods():
    validate_cookie_csrf(_request("GET", "aurora_csrf=abc", None))
    validate_cookie_csrf(_request("PATCH", "aurora_csrf=abc", "abc"))
    with pytest.raises(AuthorizationError):
        validate_cookie_csrf(_request("POST", "aurora_csrf=abc", "wrong"))
    with pytest.raises(AuthorizationError):
        validate_cookie_csrf(_request("DELETE", "aurora_csrf=abc", None))


def test_browser_token_is_http_only():
    response = Response()
    add_session_cookies(response, "example")
    cookies = response.headers.getlist("set-cookie")
    assert any("aurora_session=" in c and "httponly" in c.lower() for c in cookies)
    assert any("aurora_csrf=" in c and "httponly" not in c.lower() for c in cookies)
    clear_session_cookies(response)
    assert response.headers.getlist("set-cookie")
