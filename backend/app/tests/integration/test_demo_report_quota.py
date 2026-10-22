"""Garantías de unicidad y recuperación de autorización demo."""
import pytest

from app.core.exceptions import ConflictError
from app.services.demo_entitlement_service import (
    reserve_demo_usage,
    release_demo_usage,
)


@pytest.mark.asyncio
async def test_demo_quota_allows_one_reservation_then_denies_duplicate(session, seed_user):
    seed_user.metadata_ = {"aurora_demo_one_report": True}
    await session.commit()

    reserved = await reserve_demo_usage(session, seed_user.id)
    assert reserved is True
    await session.commit()

    with pytest.raises(ConflictError):
        await reserve_demo_usage(session, seed_user.id)
    await session.rollback()

    # Un render fallido deja la autorización disponible nuevamente.
    await release_demo_usage(session, seed_user.id)
    await session.commit()
    assert await reserve_demo_usage(session, seed_user.id) is True
    await session.commit()

    with pytest.raises(ConflictError):
        await reserve_demo_usage(session, seed_user.id)
    await session.rollback()


@pytest.mark.asyncio
async def test_regular_account_is_not_subject_to_demo_quota(session, seed_user):
    assert await reserve_demo_usage(session, seed_user.id) is False
