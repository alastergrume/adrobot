from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from app.configs.env import EnvSettings


class KeitaroSettings(EnvSettings):
    """KEITARO_* variables: connection to the Keitaro Admin API.

    In the test environment KEITARO_URL points to the fake Keitaro service
    (tests/keitaro_service), which answers like the real API.
    """

    model_config = SettingsConfigDict(env_prefix="KEITARO_")

    url: str = ""
    api_key: SecretStr = SecretStr("")
    timeout_s: float = 20.0
    # Address of the Keitaro admin for links in the browser, if it differs from KEITARO_URL
    # (e.g. in docker-compose the app reaches Keitaro by a container name).
    admin_url: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.api_key.get_secret_value())

    def admin_link(self) -> str:
        """Link to the Keitaro admin."""
        return f"{(self.admin_url or self.url).rstrip('/')}/admin/"

    def campaign_link(self, keitaro_id: int) -> str:
        """Link to the campaign in the Keitaro admin."""
        return f"{self.admin_link()}#!/campaigns/{keitaro_id}"
