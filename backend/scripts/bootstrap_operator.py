r"""Crea una cuenta propietaria con clave ingresada en consola (una sola vez).

Desde backend/:
    .venv\Scripts\python.exe scripts/bootstrap_operator.py

El script no muestra ni guarda la contraseña en un archivo. Al terminar,
configura BILLING_OPERATOR_USER_ID con el ID mostrado y reinicia la API.
"""

from __future__ import annotations

import asyncio
import getpass
import sys
from pathlib import Path

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import or_, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.user import User  # noqa: E402


async def create_operator() -> None:
    email = str(TypeAdapter(EmailStr).validate_python(input("Correo propietario: ").strip()))
    username = input("Usuario propietario: ").strip()
    if len(username) < 3:
        raise ValueError("El usuario debe tener al menos tres caracteres.")
    password = getpass.getpass("Contraseña segura (mínimo 12 caracteres): ")
    repeated = getpass.getpass("Repetir contraseña: ")
    if len(password) < 12 or password != repeated:
        raise ValueError("La contraseña no cumple la longitud mínima o no coincide.")

    async with AsyncSessionLocal() as session:
        exists = (await session.execute(select(User.id).where(or_(User.email == email, User.username == username)))).scalars().first()
        if exists is not None:
            raise ValueError("Ya existe ese correo o nombre de usuario; no se modificó ninguna cuenta.")
        user = User(email=email, username=username, password_hash=hash_password(password), status="ACTIVE")
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()

    print(f"Cuenta propietaria creada (ID {user_id}). Configura BILLING_OPERATOR_USER_ID={user_id} y reinicia la API.")


async def main() -> None:
    try:
        await create_operator()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
