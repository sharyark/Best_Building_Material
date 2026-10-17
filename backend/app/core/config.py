from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_JWT_SECRET = "change-me-in-env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Hisaab Portal"
    business_name: str = "Construction Material Supply"
    env: Literal["dev", "test", "prod"] = "dev"

    database_url: str = "postgresql+psycopg://hisaab:hisaab@localhost:5432/hisaab"
    # Dev/test convenience: build tables from the models instead of running Alembic.
    auto_create_tables: bool = False

    jwt_secret: str = INSECURE_JWT_SECRET
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    login_max_attempts: int = 5
    login_window_seconds: int = 60

    # Business defaults (see ARCHITECTURE.md section 15 for the open client questions).
    fin_year_start_month: int = 4
    currency_symbol: str = "Rs"
    workday_hours: int = 8
    overtime_multiplier: Decimal = Decimal("1.0")

    # First-run admin, created by `python -m app.bootstrap` if no users exist.
    bootstrap_admin_name: str = "Owner"
    bootstrap_admin_phone: str = "admin"
    bootstrap_admin_password: str = "admin12345"

    @model_validator(mode="after")
    def _check_prod_secrets(self) -> "Settings":
        if self.env == "prod" and self.jwt_secret == INSECURE_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set when ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
