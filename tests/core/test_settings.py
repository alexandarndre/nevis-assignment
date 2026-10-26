import pytest

from nevis_search.core.cache.settings import RedisSettings
from nevis_search.core.db.settings import PostgresSettings
from nevis_search.core.launcher.settings import LauncherSettings
from nevis_search.settings import Settings


def test_settings_compose_the_capability_mixins() -> None:
    settings = Settings()

    assert isinstance(settings, PostgresSettings)
    assert isinstance(settings, RedisSettings)
    assert isinstance(settings, LauncherSettings)


def test_settings_read_uppercase_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("RRF_K", "30")

    settings = Settings()

    assert (settings.APP_PORT, settings.RRF_K) == (9000, 30)


def test_empty_api_key_means_no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    assert Settings().ANTHROPIC_API_KEY is None
