"""YAML file extractor."""

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml

from mrcis.models.entities import EntityType, VariableEntity
from mrcis.models.extraction import ExtractionResult


class YAMLExtractor:
    """
    Extractor for YAML configuration files.

    Extracts:
    - Top-level keys
    - Nested structure paths (dot notation)
    - List items with indices
    - Anchors and aliases (resolved by PyYAML)
    """

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".yaml", ".yml"}

    def supports(self, file_path: Path) -> bool:
        """Check if this extractor supports the file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def extract(self, file_path: Path, file_id: UUID, repo_id: UUID) -> ExtractionResult:
        """
        Extract keys and structure from YAML file.

        Args:
            file_path: Path to YAML file.
            file_id: UUID of the IndexedFile record.
            repo_id: UUID of the Repository.

        Returns:
            ExtractionResult with extracted variables representing YAML keys.
        """
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="yaml",
        )

        try:
            content = file_path.read_text()
            # Use safe_load to handle anchors/aliases and avoid code execution
            data = yaml.safe_load(content)

            if data is not None:
                self._extract_keys(data, "", result, file_id, repo_id, file_path)
        except yaml.YAMLError as e:
            result.parse_errors.append(f"YAML parse error: {e}")
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
        max_depth: int = 5,
    ) -> None:
        """
        Recursively extract keys from YAML structure.

        Args:
            data: YAML data (dict, list, or scalar).
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
                        line_start=1,  # YAML doesn't provide line info easily
                        line_end=1,
                        language="yaml",
                    )
                )

                # Recurse for nested structures
                if isinstance(value, dict | list):
                    self._extract_keys(
                        value, path, result, file_id, repo_id, file_path, depth + 1, max_depth
                    )

        elif isinstance(data, list):
            # Extract list items with indices
            for idx, item in enumerate(data):
                path = f"{prefix}[{idx}]"

                # Create variable for list index
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
                        language="yaml",
                    )
                )

                # Recurse for nested structures in list items
                if isinstance(item, dict | list):
                    self._extract_keys(
                        item, path, result, file_id, repo_id, file_path, depth + 1, max_depth
                    )
