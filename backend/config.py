from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Security — must be set in .env, no default allowed in production
    secret_key: str
    access_token_expire_minutes: int = 1440

    # Database
    database_url: str = "sqlite:///./mogspar.db"

    # CORS — comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:5173"

    # Optional invite code required to register. Empty string = open registration.
    invite_code: str = ""

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
