import subprocess
import sys

from app.configs import CampaignSettings, DatabaseSettings, EnvSettings, KeitaroSettings
from app.configs.env import CONFIGS_DIR, ENV_FILE, PROJECT_ROOT


def test_all_settings_read_the_same_env_file():
    for settings_class in (DatabaseSettings, KeitaroSettings, CampaignSettings):
        assert issubclass(settings_class, EnvSettings)
        assert settings_class.model_config["env_file"] == ENV_FILE
    # conftest.py sets APP_ENV=TEST
    assert ENV_FILE == CONFIGS_DIR / ".env_test" and ENV_FILE.exists()


def env_file_for(app_env: str | None) -> str:
    """Import the settings in a fresh interpreter with the given APP_ENV."""
    env = {"PATH": ""}
    if app_env is not None:
        env["APP_ENV"] = app_env
    result = subprocess.run(
        [sys.executable, "-c", "from app.configs.env import ENV_FILE; print(ENV_FILE.name)"],
        cwd=PROJECT_ROOT, env=env, capture_output=True, text=True,
    )
    return result.stdout.strip() or result.stderr.strip().splitlines()[-1]


def test_app_env_selects_env_file():
    assert env_file_for(None) == ".env"
    assert env_file_for("PRODUCTION") == ".env"
    assert env_file_for("TEST") == ".env_test"
    assert env_file_for("test") == ".env_test"
    assert "Unknown APP_ENV" in env_file_for("STAGING")


def test_test_env_points_to_fake_keitaro():
    keitaro = KeitaroSettings()
    assert keitaro.url == "http://localhost:8081"
    assert keitaro.api_key.get_secret_value() == "test-api-key"
    assert DatabaseSettings().url.endswith("/adrobot_test")


def test_prefixes(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host:5432/db")
    monkeypatch.setenv("KEITARO_URL", "https://tracker.example")
    monkeypatch.setenv("KEITARO_API_KEY", "secret")
    monkeypatch.setenv("CAMPAIGN_GROUP", "OTHER")

    assert DatabaseSettings(_env_file=None).url == "postgresql+psycopg://u:p@host:5432/db"
    keitaro = KeitaroSettings(_env_file=None)
    assert (keitaro.url, keitaro.api_key.get_secret_value()) == ("https://tracker.example", "secret")
    assert CampaignSettings(_env_file=None).group == "OTHER"


def test_env_file_is_read(tmp_path):
    env = tmp_path / ".env"
    env.write_text("KEITARO_TIMEOUT_S=5\nCAMPAIGN_DOMAIN=example.com\n", encoding="utf-8")
    assert KeitaroSettings(_env_file=env).timeout_s == 5
    assert CampaignSettings(_env_file=env).domain == "example.com"


def test_api_key_is_hidden():
    settings = KeitaroSettings(_env_file=None, url="https://t.example", api_key="secret")
    assert "secret" not in repr(settings)


def test_is_configured():
    assert not KeitaroSettings(_env_file=None, url="", api_key="").is_configured
    assert KeitaroSettings(_env_file=None, url="https://t.example", api_key="k").is_configured


def test_links():
    settings = KeitaroSettings(_env_file=None, url="https://t.example/", api_key="k")
    assert settings.campaign_link(5) == "https://t.example/admin/#!/campaigns/5"
    # In docker-compose the app calls Keitaro by a container name, the browser needs a public address.
    settings = KeitaroSettings(_env_file=None, url="http://keitaro:8080", admin_url="http://localhost:8081", api_key="k")
    assert settings.campaign_link(5) == "http://localhost:8081/admin/#!/campaigns/5"
