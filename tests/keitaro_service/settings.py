"""Settings of the fake Keitaro service (environment variables with the FAKE_KEITARO_ prefix)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent


class KeitaroServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FAKE_KEITARO_")

    # The key the service expects in the Api-Key header (KEITARO_API_KEY of the app).
    api_key: str = "test-api-key"
    data_path: str = str(SERVICE_DIR / ".data" / "keitaro.json")


service_settings = KeitaroServiceSettings()
