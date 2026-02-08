"""JSON file extractor."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from mrcis.models.entities import EntityType, VariableEntity
from mrcis.models.extraction import ExtractionResult


class JSONExtractor:
    """Extractor for JSON configuration files."""

    def get_supported_extensions(self) -> set[str]:
        return {".json"}

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def extract(self, file_path: Path, file_id: UUID, repo_id: UUID) -> ExtractionResult:
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="json",
        )

        try:
            content = file_path.read_text()
            data = json.loads(content)
            self._extract_keys(data, "", result, file_id, repo_id, file_path)
        except json.JSONDecodeError as e:
            result.parse_errors.append(f"JSON parse error: {e}")
        except (OSError, UnicodeDecodeError) as e:
            result.parse_errors.append(f"File read error: {e}")

        return result

    def _extract_keys(
        self,
        data: dict[str, Any] | list[Any],
        prefix: str,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        file_path: Path,
        depth: int = 0,
        max_depth: int = 3,
    ) -> None:
        """Extract keys from JSON structure."""
        if depth > max_depth:
            return

        if isinstance(data, dict):
            for key, value in data.items():
                path = f"{prefix}.{key}" if prefix else key
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
                        language="json",
                    )
                )
                if isinstance(value, dict | list):
                    self._extract_keys(value, path, result, file_id, repo_id, file_path, depth + 1)
        elif isinstance(data, list):
            # For arrays, traverse into objects but don't create variables for the array itself
            for item in data:
                if isinstance(item, dict | list):
                    self._extract_keys(item, prefix, result, file_id, repo_id, file_path, depth + 1)
