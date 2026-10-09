from pydantic_settings import SettingsConfigDict

from app.configs.env import EnvSettings


class CampaignSettings(EnvSettings):
    """CAMPAIGN_* variables: defaults for campaigns made by the campaign creator.

    Domain, group and traffic source are looked up in Keitaro by these names.
    """

    model_config = SettingsConfigDict(env_prefix="CAMPAIGN_")

    domain: str = "in.posdk.xyz"
    group: str = "FORTESTS"
    source: str = "FORTESTS"
    geo_redirect_url: str = "https://google.com"
