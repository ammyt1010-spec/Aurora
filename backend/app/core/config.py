from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://colmena:colmena@localhost:5432/colmena"
    database_url_sync: str = "postgresql+psycopg://colmena:colmena@localhost:5432/colmena"

    api_v1_prefix: str = "/api/v1"

    default_page_size: int = 25
    max_page_size: int = 200

    export_storage_dir: str = "./exports_storage"
    max_export_rows: int = 200_000

    jwt_secret_key: str = "dev-only-insecure-secret-change-me-in-production-please-1234567890"
    billing_operator_email: str = ""  # Cuenta central que aprueba pagos y administra precios.
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    cors_origins: list[str] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
    ]
    demo_access_enabled: bool = False
    demo_user_email: str = "demo@aurora.local"

    # E-17: protección anti-abuso mínima del formulario público (sin Redis —
    # limitación conocida en despliegues multi-worker, documentada en
    # app/core/rate_limit.py).
    login_rate_limit_max: int = 20
    login_rate_limit_window_seconds: int = 900
    register_rate_limit_max: int = 5
    register_rate_limit_window_seconds: int = 3600
    public_session_rate_limit_max: int = 10
    public_session_rate_limit_window_seconds: int = 60

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.lower() == "production":
            if len(self.jwt_secret_key) < 48 or self.jwt_secret_key.startswith("dev-only") or "change-me" in self.jwt_secret_key.lower():
                raise ValueError("JWT_SECRET_KEY debe tener al menos 48 caracteres aleatorios en producción.")
            if self.demo_access_enabled:
                raise ValueError("No se permite DEMO_ACCESS_ENABLED en producción.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
