import importlib.util
import inspect
from functools import lru_cache
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.metadata_provider import MetadataProvider

logger = get_logger(__name__)


@lru_cache
def load_plugin_providers() -> tuple[MetadataProvider, ...]:
    """Instances of every MetadataProvider defined by a module in PROVIDER_PLUGINS_DIR."""
    if not settings.PROVIDER_PLUGINS_DIR:
        return ()
    providers = []
    for path in sorted(Path(settings.PROVIDER_PLUGINS_DIR).glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"ludexis_provider_plugin_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            providers += [
                cls()
                for _, cls in inspect.getmembers(module, inspect.isclass)
                if issubclass(cls, MetadataProvider) and cls.__module__ == module.__name__ and not inspect.isabstract(cls)
            ]
        except Exception:
            # One broken plugin must not keep the server from starting.
            logger.exception("Provider plugin failed to load", extra={"path": str(path)})
    return tuple(providers)
