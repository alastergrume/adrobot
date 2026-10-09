"""Base class for all settings: values come from environment variables and an env file
in app/configs, chosen by APP_ENV:

    APP_ENV=PRODUCTION (default) -> app/configs/.env
    APP_ENV=TEST                 -> app/configs/.env_test  (fake Keitaro and the test database)
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIGS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIGS_DIR.parents[1]

ENV_FILES = {
    "PRODUCTION": CONFIGS_DIR / ".env",
    "TEST": CONFIGS_DIR / ".env_test",
}


def current_env() -> str:
    env = os.environ.get("APP_ENV", "PRODUCTION").strip().upper()
    if env not in ENV_FILES:
        raise ValueError(f"Unknown APP_ENV={env!r}, expected one of: {', '.join(ENV_FILES)}")
    return env


APP_ENV = current_env()
# Absolute path, so the app and Alembic find it from any working directory.
ENV_FILE = ENV_FILES[APP_ENV]


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        # Validation errors must not print values from the environment (API keys, passwords).
        hide_input_in_errors=True,
    )
