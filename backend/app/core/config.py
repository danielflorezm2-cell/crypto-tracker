from pydantic_settings import BaseSettings, ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(extra="ignore")
    cors_origins: str = "http://localhost:5173"
    binance_rest_url: str = "https://data-api.binance.vision"
    binance_api_key: str = ""
    database_url: str
    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    

settings = Settings()