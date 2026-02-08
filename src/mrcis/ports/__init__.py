"""Port interfaces for MRCIS.

Ports define the contracts that adapters must implement, following the
Dependency Inversion Principle. Application logic depends only on these
abstractions, not concrete implementations.
"""

from mrcis.ports.db_session import DbSessionPort
from mrcis.ports.embedder import EmbedderPort
from mrcis.ports.extractors import ExtractorPort, ExtractorRegistryPort
from mrcis.ports.relation_graph import RelationGraphPort
from mrcis.ports.state import (
    FileReaderPort,
    FileWriterPort,
    IndexingStatePort,
    QueuePort,
    RepositoryReaderPort,
    RepositoryWriterPort,
    StatePort,
)
from mrcis.ports.vector_store import VectorStorePort

__all__ = [
    "DbSessionPort",
    "EmbedderPort",
    "ExtractorPort",
    "ExtractorRegistryPort",
    "FileReaderPort",
    "FileWriterPort",
    "IndexingStatePort",
    "QueuePort",
    "RelationGraphPort",
    "RepositoryReaderPort",
    "RepositoryWriterPort",
    "StatePort",
    "VectorStorePort",
]
