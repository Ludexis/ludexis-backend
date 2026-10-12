from unittest.mock import patch

import pytest

from app.core.access import restricted_providers
from app.core.config import settings
from app.providers.plugins import load_plugin_providers
from app.services.metadata import MetadataService
from app.services.settings import match_provider_names

PLUGIN = '''
from app.providers.metadata_provider import MetadataProvider


class ExampleProvider(MetadataProvider):
    name = "Example"
    restricted = True

    def search(self, query, limit=20, developer=None):
        return []

    def get_details(self, external_id):
        return None
'''


@pytest.fixture
def plugin_dir(tmp_path):
    load_plugin_providers.cache_clear()
    with patch.object(settings, "PROVIDER_PLUGINS_DIR", str(tmp_path)):
        yield tmp_path
    load_plugin_providers.cache_clear()


def test_plugin_provider_is_registered_and_restricted(plugin_dir):
    (plugin_dir / "example.py").write_text(PLUGIN)
    (plugin_dir / "broken.py").write_text("this is not python")

    assert [provider.name for provider in load_plugin_providers()] == ["Example"]
    assert "Example" in MetadataService().provider_map
    assert match_provider_names() == ["VNDB", "IGDB", "Steam", "Example"]
    assert restricted_providers() == {"VNDB", "Example"}


def test_no_plugin_folder_keeps_built_in_providers(plugin_dir):
    with patch.object(settings, "PROVIDER_PLUGINS_DIR", ""):
        assert load_plugin_providers() == ()
        assert match_provider_names() == ["VNDB", "IGDB", "Steam"]
        assert restricted_providers() == {"VNDB"}
