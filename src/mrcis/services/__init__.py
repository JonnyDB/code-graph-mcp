"""MRCIS services layer.

Services coordinate between extractors, storage, and the MCP interface.
"""

from mrcis.services.embedder import EmbeddingService
from mrcis.services.indexer import IndexingService
from mrcis.services.resolver import ReferenceResolver, ResolutionResult
from mrcis.services.watcher import FileEvent, FileWatcher

__all__ = [
    "EmbeddingService",
    "FileEvent",
    "FileWatcher",
    "IndexingService",
    "ReferenceResolver",
    "ResolutionResult",
]
