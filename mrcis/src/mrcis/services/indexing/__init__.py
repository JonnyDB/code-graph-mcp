"""Indexing services package."""

from mrcis.services.indexing.failure_policy import IndexFailurePolicy
from mrcis.services.indexing.language import LanguageDetector
from mrcis.services.indexing.pipeline import FileIndexingPipeline
from mrcis.services.indexing.scanner import RepositoryScanner
from mrcis.services.indexing.stats_updater import RepositoryStatsUpdater
from mrcis.services.indexing.text_builder import EmbeddingTextBuilder

__all__ = [
    "EmbeddingTextBuilder",
    "FileIndexingPipeline",
    "IndexFailurePolicy",
    "LanguageDetector",
    "RepositoryScanner",
    "RepositoryStatsUpdater",
]
