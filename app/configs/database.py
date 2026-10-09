from pydantic_settings import SettingsConfigDict

from app.configs.env import EnvSettings


class DatabaseSettings(EnvSettings):
    """DATABASE_URL. Defaults to the "db" service of docker/docker-compose.yml."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = "postgresql+psycopg://adrobot:adrobot@localhost:5432/adrobot"
