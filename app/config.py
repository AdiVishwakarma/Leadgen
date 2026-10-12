from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://leadgen:leadgen@localhost:5432/leadgen"
    google_places_api_key: str = ""
    gemini_api_key: str = ""
    # Model names change often. If you get a 404, check the current free-tier model in Google AI Studio.
    gemini_model: str = "gemini-2.5-flash"
    sender_name: str = "Aditya"
    vercel_token: str = ""
    vercel_team_id: str = ""  # only if you deploy under a team, else leave empty


settings = Settings()
