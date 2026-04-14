from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    cron_secret: str = "dev-secret"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
