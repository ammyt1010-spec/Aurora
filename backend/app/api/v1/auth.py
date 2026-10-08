from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import enforce_login_rate_limit, enforce_registration_rate_limit
from app.core.auth_cookie import add_session_cookies, clear_session_cookies
from app.core.exceptions import AuthenticationError
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201,
    dependencies=[Depends(enforce_registration_rate_limit)])
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    user = await service.register(payload)
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)])
async def login(payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    token = await service.login(payload)
    add_session_cookies(response, token)
    return TokenResponse(access_token=token)


@router.post("/demo-login", response_model=TokenResponse)
async def demo_login(request: Request, response: Response, session: AsyncSession = Depends(get_db)):
    settings = get_settings()
    client_host = request.client.host if request.client else ""
    if settings.environment == "production" or not settings.demo_access_enabled:
        raise AuthenticationError("El acceso demo no está disponible.")
    if client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise AuthenticationError("El acceso demo solo está disponible desde el servidor local.")
    service = AuthService(session)
    token = await service.demo_login(settings.demo_user_email)
    add_session_cookies(response, token)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return UserRead.model_validate(current_user)

@router.post("/logout", status_code=204)
async def logout(response: Response, _user: User = Depends(get_current_user)):
    """Revoke the browser cookie in this client (bearer tokens expire naturally)."""
    clear_session_cookies(response)
    return None
