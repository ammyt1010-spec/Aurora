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
    billing_operator_user_id: int | None = None  # Establece este ID después de un alta segura del operador.
    session_maintenance_operator_user_id: int | None = None  # Operador interno explícitamente autorizado para purgas globales.
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
        env = self.environment.lower()
        if env in {"production", "staging"}:
            if len(self.jwt_secret_key) < 48 or self.jwt_secret_key.startswith("dev-only") or "change-me" in self.jwt_secret_key.lower():
                raise ValueError("JWT_SECRET_KEY debe tener al menos 48 caracteres aleatorios en producción o staging.")
        if self.demo_access_enabled:
            if env in {"production", "staging"}:
                raise ValueError("No se permite DEMO_ACCESS_ENABLED en entornos de producción o staging.")
            if env not in {"development", "test", "local"}:
                raise ValueError(f"No se permite DEMO_ACCESS_ENABLED en el entorno '{env}'. Solo está permitido en desarrollo local aislado.")
            for origin in self.cors_origins:
                clean_origin = origin.strip().lower()
                if "0.0.0.0" in clean_origin:
                    raise ValueError("No se permite DEMO_ACCESS_ENABLED con 0.0.0.0 en CORS_ORIGINS.")
                if clean_origin.startswith("https://") or ("localhost" not in clean_origin and "127.0.0.1" not in clean_origin):
                    raise ValueError("No se permite DEMO_ACCESS_ENABLED cuando CORS_ORIGINS contiene dominios públicos o HTTPS.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
