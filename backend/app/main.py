from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.core.database import engine
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

settings = get_settings()

configure_logging()

app = FastAPI(
    title="AURORA Professional API",
    description=(
        "Backend unificado de Colmena (proyectos académicos, CENSOPAS-COPSOQ, "
        "surveys, motor estadístico, autenticación). Fases 1-9 implementadas."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"], include_in_schema=False)
async def readiness():
    """Readiness is only successful when the database responds."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ready"}
