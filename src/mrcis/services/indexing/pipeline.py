"""File indexing pipeline for processing individual files.

Handles single-file processing through the full indexing pipeline:
extract entities → generate embeddings → store results.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from loguru import logger

from mrcis.extractors.context import ExtractionContext
from mrcis.models.state import IndexedFile
from mrcis.services.indexing.text_builder import EmbeddingTextBuilder

if TYPE_CHECKING:
    from mrcis.ports import (
        EmbedderPort,
        ExtractorRegistryPort,
        RelationGraphPort,
        VectorStorePort,
    )


@dataclass
class ProcessingResult:
    """Result of processing a file through the pipeline."""

    entity_count: int
    parse_errors: list[str] | None = None


class FileIndexingPipeline:
    """Processes individual files through the indexing pipeline.

    Responsible for single-file processing:
    1. Clean up existing data (idempotency)
    2. Extract entities using appropriate extractor
    3. Generate embeddings for entities
    4. Store vectors and entities
    5. Store relations and pending references

    The pipeline is stateless and focused solely on file processing.
    Queue management and orchestration are handled by IndexingService.
    """

    def __init__(
        self,
        vector_store: "VectorStorePort",
        relation_graph: "RelationGraphPort",
        extractor_registry: "ExtractorRegistryPort",
        embedder: "EmbedderPort",
    ) -> None:
        """Initialize pipeline with dependencies.

        Args:
            vector_store: Vector storage port
            relation_graph: Relation graph port
            extractor_registry: Extractor registry port
            embedder: Embedding service port
        """
        self.vector_store = vector_store
        self.relation_graph = relation_graph
        self.extractors = extractor_registry
        self.embedder = embedder
        self.text_builder = EmbeddingTextBuilder()

    async def process(
        self,
        file: IndexedFile,
        full_path: Path,
        language: str | None,
    ) -> ProcessingResult:
        """Process a single file through the indexing pipeline.

        This method is idempotent: existing data is cleaned up before
        re-processing, ensuring crash recovery works correctly.

        Args:
            file: File metadata from database
            full_path: Full filesystem path to the file
            language: Detected language (optional)

        Returns:
            ProcessingResult with entity count and any parse errors
        """
        logger.info("Processing file: id={} path={}", file.id, file.path)

        # Clean up any existing data from previous attempts (idempotency).
        # This handles crash recovery where partial data may exist from
        # a previous incomplete processing run.
        await self.vector_store.delete_by_file(str(file.id))
        await self.relation_graph.delete_entities_for_file(str(file.id))

        # Get appropriate extractor
        extractor = self.extractors.get_extractor(full_path)
        if not extractor:
            logger.debug("No extractor found for {}", full_path)
            return ProcessingResult(entity_count=0)

        # Extract entities and relations using context
        context = ExtractionContext(
            file_path=full_path,
            file_id=file.id,
            repository_id=file.repository_id,
            language=language,
        )
        result = await extractor.extract_with_context(context)

        parse_errors = result.parse_errors if result.parse_errors else None
        if parse_errors:
            logger.warning("Parse errors encountered: {}", parse_errors)

        # Generate embeddings for all entities
        entities = result.all_entities()
        if not entities:
            return ProcessingResult(entity_count=0, parse_errors=parse_errors)

        # Build embedding texts
        texts = [self.text_builder.build(e) for e in entities]

        # Generate embeddings
        vectors = await self.embedder.embed_texts(texts)

        # Build vector records using the dynamic model (dimensions from config)
        CodeVectorModel = self.vector_store.model
        vector_records: list[Any] = []

        for entity, vector, text in zip(entities, vectors, texts, strict=True):
            vector_id = str(uuid4())
            entity.vector_id = vector_id

            # Build vector instance for storage
            vector_records.append(
                CodeVectorModel(
                    id=vector_id,
                    repository_id=str(file.repository_id),
                    file_id=str(file.id),
                    qualified_name=entity.qualified_name,
                    simple_name=entity.name,
                    entity_type=(
                        entity.entity_type
                        if isinstance(entity.entity_type, str)
                        else entity.entity_type.value
                    ),
                    language=language or "unknown",
                    file_path=file.path,
                    line_start=entity.line_start,
                    line_end=entity.line_end,
                    vector=vector,
                    embedding_text=text,
                    visibility=str(getattr(entity, "visibility", "public")),
                    is_exported=bool(getattr(entity, "is_exported", False)),
                    has_docstring=bool(entity.docstring),
                    signature=getattr(entity, "signature", None),
                    docstring=entity.docstring,
                )
            )

            # Store entity in relation graph with caller-provided ID
            await self.relation_graph.add_entity(
                repository_id=str(file.repository_id),
                file_id=str(file.id),
                qualified_name=entity.qualified_name,
                simple_name=entity.name,
                entity_type=entity.entity_type,
                language=language or "unknown",
                line_start=entity.line_start,
                line_end=entity.line_end,
                col_start=entity.col_start,
                col_end=entity.col_end,
                signature=getattr(entity, "signature", None),
                docstring=entity.docstring,
                source_text=entity.source_text,
                visibility=str(getattr(entity, "visibility", "public")),
                is_exported=bool(getattr(entity, "is_exported", False)),
                decorators=entity.decorators if entity.decorators else None,
                entity_id=str(entity.id),
                vector_id=vector_id,
            )

        # Store vectors in vector DB
        await self.vector_store.upsert_vectors(vector_records)

        # Store resolved relations individually
        for rel in result.relations:
            if rel.target_id is not None:
                await self.relation_graph.add_relation(
                    source_id=str(rel.source_id),
                    target_id=str(rel.target_id),
                    relation_type=str(rel.relation_type),
                    line_number=rel.line_number,
                    context_snippet=rel.context_snippet,
                    weight=rel.weight,
                )

        # Queue pending references for deferred resolution
        for ref in result.pending_references:
            await self.relation_graph.add_pending_reference(
                source_entity_id=str(ref.source_entity_id),
                source_qualified_name=ref.source_qualified_name,
                source_repository_id=str(ref.source_repository_id),
                target_qualified_name=ref.target_qualified_name,
                relation_type=str(ref.relation_type),
                line_number=ref.line_number,
                context_snippet=ref.context_snippet,
                receiver_expr=ref.receiver_expr,
            )

        return ProcessingResult(
            entity_count=len(entities),
            parse_errors=parse_errors,
        )
