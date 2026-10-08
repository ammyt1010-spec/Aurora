from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, payload: RegisterRequest) -> User:
        existing = await self.session.execute(
            select(User).where((User.email == payload.email) | (User.username == payload.username))
        )
        if existing.scalars().first() is not None:
            raise ConflictError("Ya existe un usuario con ese email o username.")

        user = User(
            email=payload.email,
            username=payload.username,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            status="ACTIVE",
        )
        self.session.add(user)
        await self.session.flush()

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def login(self, payload: LoginRequest) -> str:
        result = await self.session.execute(select(User).where(User.email == payload.email))
        user = result.scalars().first()
        if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
            raise AuthenticationError("Email o contraseña incorrectos.")
        if user.status != "ACTIVE":
            raise AuthenticationError("El usuario no está activo.")

        return create_access_token(user.id)

    async def demo_login(self, email: str) -> str:
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if user is None:
            user = User(email=email, username="demo", first_name="Supervisor", status="ACTIVE")
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

        return create_access_token(user.id)

