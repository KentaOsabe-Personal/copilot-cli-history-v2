"""Pure Python Copilot CLI history reader contracts."""

from copilot_history.catalog_reader import SessionCatalogReader
from copilot_history.current_reader import CurrentSessionReader
from copilot_history.event_normalizer import EventNormalizer
from copilot_history.legacy_reader import LegacySessionReader
from copilot_history.projections import (
    ActivityProjector,
    ConversationProjector,
    SearchTextProjector,
)
from copilot_history.root_resolver import RootResolver
from copilot_history.source_catalog import SourceCatalog
from copilot_history.types import ReadFailureResult, ReadSuccessResult

__all__ = (
    "ActivityProjector",
    "ConversationProjector",
    "CurrentSessionReader",
    "EventNormalizer",
    "LegacySessionReader",
    "ReadFailureResult",
    "ReadSuccessResult",
    "RootResolver",
    "SearchTextProjector",
    "SessionCatalogReader",
    "SourceCatalog",
)
