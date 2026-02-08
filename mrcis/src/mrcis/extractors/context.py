"""Extraction context for standardized extractor interface.

Provides a consistent data structure for passing extraction parameters
to all extractors, improving the Liskov Substitution Principle compliance
by ensuring all extractors receive the same context information.
"""

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExtractionContext(BaseModel):
    """Context object for code extraction operations.

    Encapsulates all information needed by an extractor to process a file.
    Using a context object (vs positional parameters) provides:
    - Easier future extension (add fields without changing signatures)
    - Consistent interface across all extractors (LSP)
    - Clear documentation of what data is available

    Attributes:
        file_path: Absolute path to the file being extracted.
        file_id: UUID of the IndexedFile record.
        repository_id: UUID of the Repository.
        language: Optional language identifier (e.g., "python", "typescript").
        source_bytes: Optional pre-read file content (for optimization).
    """

    model_config = ConfigDict(frozen=True)

    file_path: Path
    file_id: UUID
    repository_id: UUID
    language: str | None = None
    source_bytes: bytes | None = None
