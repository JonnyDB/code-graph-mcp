"""Embedding text builder for code entities.

Constructs text representations of code entities for embedding generation.
"""

from typing import Any


class EmbeddingTextBuilder:
    """Builds text representations of code entities for embeddings.

    Combines entity metadata (type, name, signature, docstring, source)
    into a structured text format optimized for semantic search.
    """

    def build(self, entity: Any) -> str:
        """Build text representation for embedding.

        Args:
            entity: Code entity with metadata (qualified_name, entity_type, etc.)

        Returns:
            Formatted text string for embedding generation

        The format is:
            <type>: <qualified_name>
            Signature: <signature>  (if present)
            Description: <docstring>  (if present)
            Code:
            <source_text>  (if present, truncated to 2000 chars)
        """
        # Handle both enum and string entity types
        etype = (
            entity.entity_type if isinstance(entity.entity_type, str) else entity.entity_type.value
        )

        parts = [
            f"{etype}: {entity.qualified_name}",
        ]

        # Add signature if available
        if getattr(entity, "signature", None):
            parts.append(f"Signature: {entity.signature}")

        # Add docstring if available
        if entity.docstring:
            parts.append(f"Description: {entity.docstring}")

        # Add source text if available (truncated)
        if hasattr(entity, "source_text") and entity.source_text:
            # Truncate source if too long
            source = entity.source_text[:2000]
            parts.append(f"Code:\n{source}")

        return "\n".join(parts)
