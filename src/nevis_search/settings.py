from functools import lru_cache

from nevis_search.core.cache.settings import RedisSettings
from nevis_search.core.db.settings import PostgresSettings
from nevis_search.core.launcher.settings import LauncherSettings
from nevis_search.core.settings.general import GeneralSettings
from nevis_search.embeddings.settings import EmbeddingSettings
from nevis_search.search.settings import SearchSettings
from nevis_search.summary.settings import SummarySettings


class Settings(
    GeneralSettings,
    LauncherSettings,
    PostgresSettings,
    RedisSettings,
    EmbeddingSettings,
    SearchSettings,
    SummarySettings,
):
    pass


@lru_cache
def get_settings() -> Settings:
    return Settings()
