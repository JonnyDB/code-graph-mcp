"""TOML file extractor."""

import tomllib
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from mrcis.models.entities import EntityType, VariableEntity
from mrcis.models.extraction import ExtractionResult


class TOMLExtractor:
    """
    Extractor for TOML configuration files.

    Extracts:
    - Table names (sections)
    - Key-value pairs
    - Nested tables
    - Array of tables
    - Nested structures with dot notation
    """

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".toml"}

    def supports(self, file_path: Path) -> bool:
        """Check if this extractor supports the file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def extract(self, file_path: Path, file_id: UUID, repo_id: UUID) -> ExtractionResult:
        """
        Extract keys and structure from TOML file.

        Args:
            file_path: Path to TOML file.
            file_id: UUID of the IndexedFile record.
            repo_id: UUID of the Repository.

        Returns:
            ExtractionResult with extracted variables representing TOML keys.
        """
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="toml",
        )

        try:
            content = file_path.read_bytes()
            # Use tomllib (Python 3.11+) for parsing
            data = tomllib.loads(content.decode("utf-8"))

            if data is not None:
                self._extract_keys(data, "", result, file_id, repo_id, file_path)
        except tomllib.TOMLDecodeError as e:
            result.parse_errors.append(f"TOML parse error: {e}")
        except Exception as e:
            result.parse_errors.append(f"Unexpected error: {e}")

        return result

    def _extract_keys(
        self,
        data: Any,
        prefix: str,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        file_path: Path,
        depth: int = 0,
        max_depth: int = 10,
    ) -> None:
        """
        Recursively extract keys from TOML structure.

        Args:
            data: TOML data (dict, list, or scalar).
            prefix: Current path prefix (dot notation).
            result: ExtractionResult to populate.
            file_id: UUID of the file.
            repo_id: UUID of the repository.
            file_path: Path to the file.
            depth: Current nesting depth.
            max_depth: Maximum depth to traverse.
        """
        if depth > max_depth:
            return

        if isinstance(data, dict):
            # Create variable for the table itself (if it has a prefix)
            if prefix:
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=prefix.rsplit(".", maxsplit=1)[-1],
                        qualified_name=prefix,
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=1,  # TOML doesn't provide line info easily
                        line_end=1,
                        language="toml",
                    )
                )

            # Extract all keys in this table
            for key, value in data.items():
                # Build qualified name with dot notation
                path = f"{prefix}.{key}" if prefix else key

                # Create variable entity for this key
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=key,
                        qualified_name=path,
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=1,
                        line_end=1,
                        language="toml",
                    )
                )

                # Recurse for nested structures
                if isinstance(value, dict | list):
                    self._extract_keys(
                        value,
                        path,
                        result,
                        file_id,
                        repo_id,
                        file_path,
                        depth + 1,
                        max_depth,
                    )

        elif isinstance(data, list):
            # Extract list items - could be array of tables or simple arrays
            for idx, item in enumerate(data):
                path = f"{prefix}[{idx}]"

                # Create variable for array of tables entry
                if isinstance(item, dict):
                    result.variables.append(
                        VariableEntity(
                            id=uuid4(),
                            name=f"[{idx}]",
                            qualified_name=path,
                            entity_type=EntityType.VARIABLE,
                            repository_id=repo_id,
                            file_id=file_id,
                            file_path=str(file_path),
                            line_start=1,
                            line_end=1,
                            language="toml",
                        )
                    )

                # Recurse for nested structures in list items
                if isinstance(item, dict | list):
                    self._extract_keys(
                        item,
                        path,
                        result,
                        file_id,
                        repo_id,
                        file_path,
                        depth + 1,
                        max_depth,
                    )
