"""Ready-to-use settings objects. Modules import them from here:

    from app.configs import keitaro_settings
"""

from app.configs.campaign import CampaignSettings
from app.configs.database import DatabaseSettings
from app.configs.env import EnvSettings
from app.configs.keitaro import KeitaroSettings

database_settings = DatabaseSettings()
keitaro_settings = KeitaroSettings()
campaign_settings = CampaignSettings()

__all__ = [
    "EnvSettings",
    "DatabaseSettings",
    "KeitaroSettings",
    "CampaignSettings",
    "database_settings",
    "keitaro_settings",
    "campaign_settings",
]
