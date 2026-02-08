"""Markdown documentation extractor."""

import re
from pathlib import Path
from uuid import UUID, uuid4

from mrcis.models.entities import EntityType, ImportEntity, VariableEntity
from mrcis.models.extraction import ExtractionResult


class MarkdownExtractor:
    """
    Extractor for Markdown documentation files.

    Extracts:
    - Headings (as hierarchical structure stored in variables)
    - Code blocks (with language tags)
    - Links (inline and reference-style)
    """

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".md", ".markdown"}

    def supports(self, file_path: Path) -> bool:
        """Check if this extractor supports the given file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def extract(  # noqa: PLR0915
        self, file_path: Path, file_id: UUID, repo_id: UUID
    ) -> ExtractionResult:
        """Extract entities from Markdown file."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="markdown",
        )

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            result.parse_errors.append(f"Failed to read file: {e}")
            return result

        # Track heading hierarchy for building qualified names
        heading_stack: list[tuple[int, str]] = []

        lines = content.split("\n")
        in_code_block = False
        code_block_lines: list[str] = []
        code_block_lang: str | None = None
        code_block_start_line = 0
        code_block_counter = 0

        for line_num, line in enumerate(lines, start=1):
            # Handle code blocks (fenced with ```)
            if line.strip().startswith("```"):
                if not in_code_block:
                    # Start of code block
                    in_code_block = True
                    code_block_start_line = line_num
                    code_block_lines = []
                    # Extract language tag if present
                    lang_match = re.match(r"```(\w+)", line.strip())
                    code_block_lang = lang_match.group(1) if lang_match else None
                else:
                    # End of code block
                    in_code_block = False
                    code_block_counter += 1
                    block_name = f"code_block_{code_block_counter}"

                    # Build qualified name based on current heading context
                    qualified_name = self._build_qualified_name(block_name, heading_stack)

                    # Store code block as variable
                    result.variables.append(
                        VariableEntity(
                            id=uuid4(),
                            name=block_name,
                            qualified_name=qualified_name,
                            entity_type=EntityType.VARIABLE,
                            repository_id=repo_id,
                            file_id=file_id,
                            file_path=str(file_path),
                            line_start=code_block_start_line,
                            line_end=line_num,
                            language="markdown",
                            docstring=f"Code block (language: {code_block_lang or 'unknown'})",
                            annotations={"language": code_block_lang or "unknown"},
                        )
                    )
                    code_block_lang = None
                continue

            if in_code_block:
                code_block_lines.append(line)
                continue

            # Extract headings (ATX-style: # Heading)
            heading_match = re.match(r"^(#{1,6})\s+(.+?)(?:\s*\{#.*\})?\s*$", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                # Update heading stack for hierarchy
                # Remove all headings at same or deeper level
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()

                # Add this heading to stack
                heading_stack.append((level, heading_text))

                # Build qualified name from heading hierarchy
                qualified_name = ".".join(h[1] for h in heading_stack)

                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=heading_text,
                        qualified_name=qualified_name,
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=line_num,
                        line_end=line_num,
                        language="markdown",
                        docstring=f"Heading level {level}",
                        annotations={"heading_level": str(level)},
                    )
                )

            # Extract inline links: [text](url)
            inline_links = re.finditer(r'\[([^\]]+)\]\(([^)]+?)(?:\s+"([^"]+)")?\)', line)
            for match in inline_links:
                link_text = match.group(1)
                link_url = match.group(2)

                # Determine if relative or absolute link
                is_relative = not link_url.startswith(("http://", "https://", "//"))

                result.imports.append(
                    ImportEntity(
                        id=uuid4(),
                        name=link_text,
                        qualified_name=link_url,
                        entity_type=EntityType.IMPORT,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=line_num,
                        line_end=line_num,
                        language="markdown",
                        source_module=link_url,
                        imported_symbols=[link_text],
                        is_relative=is_relative,
                    )
                )

            # Extract reference-style link definitions: [id]: url "title"
            ref_link_match = re.match(r'^\[([^\]]+)\]:\s+(\S+)(?:\s+"([^"]+)")?\s*$', line)
            if ref_link_match:
                ref_id = ref_link_match.group(1)
                ref_url = ref_link_match.group(2)

                is_relative = not ref_url.startswith(("http://", "https://", "//"))

                result.imports.append(
                    ImportEntity(
                        id=uuid4(),
                        name=ref_id,
                        qualified_name=ref_url,
                        entity_type=EntityType.IMPORT,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=line_num,
                        line_end=line_num,
                        language="markdown",
                        source_module=ref_url,
                        imported_symbols=[ref_id],
                        is_relative=is_relative,
                    )
                )

            # Extract image links: ![alt](url)
            image_links = re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", line)
            for match in image_links:
                alt_text = match.group(1)
                image_url = match.group(2)
                is_relative = not image_url.startswith(("http://", "https://", "//"))

                result.imports.append(
                    ImportEntity(
                        id=uuid4(),
                        name=alt_text or "image",
                        qualified_name=image_url,
                        entity_type=EntityType.IMPORT,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=line_num,
                        line_end=line_num,
                        language="markdown",
                        source_module=image_url,
                        imported_symbols=[alt_text or "image"],
                        is_relative=is_relative,
                    )
                )

        return result

    def _build_qualified_name(self, name: str, heading_stack: list[tuple[int, str]]) -> str:
        """Build qualified name from heading hierarchy."""
        if not heading_stack:
            return name
        parent_path = ".".join(h[1] for h in heading_stack)
        return f"{parent_path}.{name}"
