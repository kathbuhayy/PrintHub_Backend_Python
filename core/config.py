from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = ""
    DIRECT_URL: str = ""

    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    PAYMONGO_SECRET_KEY: str = ""
    PAYMONGO_WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3001"

    EMAIL_USER: str = ""
    EMAIL_PASS: str = ""

    FAL_KEY: str = ""
    FAL_MOCK: str = "true"

    MESHY_API_KEY: str = ""

    PORT: int = 8000
    NODE_ENV: str = "development"

    @property
    def is_production(self) -> bool:
        return self.NODE_ENV == "production"

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.EMAIL_USER and self.EMAIL_PASS)

    @property
    def fal_mock(self) -> bool:
        return self.FAL_MOCK.lower() == "true"


settings = Settings()
