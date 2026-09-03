from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    cors_origins: str = "http://localhost:5173"
    binance_api_key: str = "https://data-api.binance.vision"

    database_url: str
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    #binance_rest_url: str = "https://data-api.binance.vision"

settings = Settings()