"""Shared public-survey rate limiting.

PostgreSQL uses an atomic upsert; separate Uvicorn workers therefore share
one quota. In-memory buckets remain only for SQLite test/development.
No client IP is stored: the bucket key is HMAC-hashed.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import RateLimitExceededError

_buckets: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    secret = get_settings().jwt_secret_key.encode("utf-8")
    return hmac.new(secret, host.encode("utf-8"), hashlib.sha256).hexdigest()


async def enforce_public_session_rate_limit(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> None:
    settings = get_settings()
    key = _client_key(request)
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "postgresql":
        result = await session.execute(
            text("""
                INSERT INTO colmena.public_rate_limits (key, window_start, counter)
                VALUES (:key, CURRENT_TIMESTAMP, 1)
                ON CONFLICT (key) DO UPDATE SET
                  counter = CASE
                    WHEN colmena.public_rate_limits.window_start
                      + make_interval(secs => :window_seconds) <= CURRENT_TIMESTAMP
                    THEN 1 ELSE colmena.public_rate_limits.counter + 1 END,
                  window_start = CASE
                    WHEN colmena.public_rate_limits.window_start
                      + make_interval(secs => :window_seconds) <= CURRENT_TIMESTAMP
                    THEN CURRENT_TIMESTAMP ELSE colmena.public_rate_limits.window_start END
                RETURNING counter
            """),
            {"key": key, "window_seconds": settings.public_session_rate_limit_window_seconds},
        )
        counter = result.scalar_one()
        # Commit the quota even for rejected requests. This is independent of
        # the transaction that subsequently creates the response session.
        await session.commit()
        if counter > settings.public_session_rate_limit_max:
            raise RateLimitExceededError(
                "Demasiadas solicitudes; intenta nuevamente más tarde.",
                retry_after_seconds=settings.public_session_rate_limit_window_seconds,
            )
        return

    if settings.environment.lower() == "production":
        raise RuntimeError("La protección de sesiones públicas requiere PostgreSQL en producción.")

    now = time.monotonic()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > settings.public_session_rate_limit_window_seconds:
        bucket.popleft()
    if len(bucket) >= settings.public_session_rate_limit_max:
        raise RateLimitExceededError(
            "Demasiadas solicitudes; intenta nuevamente más tarde.",
            retry_after_seconds=settings.public_session_rate_limit_window_seconds,
        )
    bucket.append(now)
