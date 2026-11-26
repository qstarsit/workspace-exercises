from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings read from ``HERMES_*`` env vars and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="HERMES_", env_file=".env", extra="ignore"
    )

    base_url: str = "https://hermes.brinkhorst.dev"
    api_key: SecretStr | None = None
    timeout_seconds: float = Field(default=10.0, gt=0)

    @property
    def api_base_url(self) -> str:
        """Base URL of the versioned Hermes API."""
        return f"{self.base_url.rstrip('/')}/api/v1"

    @property
    def request_headers(self) -> dict[str, str]:
        """Headers sent with every Hermes request; includes the API key if set."""
        if self.api_key is None:
            return {}
        return {"X-API-Key": self.api_key.get_secret_value()}
