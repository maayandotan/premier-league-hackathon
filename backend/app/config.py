"""Settings, read from environment variables or the repo-root .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    azure_speech_key: str = ""
    azure_speech_region: str = "francecentral"
    foundry_project_endpoint: str = ""
    foundry_model_deployment: str = ""
    use_agents: bool = True  # False = template commentary only (tests, CI, no Azure access)

    frontend_origin: str = "http://localhost:5173"
    replay_speed: float = 1.0  # 1.0 = real time; higher replays the match faster


settings = Settings()
