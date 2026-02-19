"""Base extractor classes and protocols."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import UUID

from tree_sitter import Language, Node, Parser, Tree
from tree_sitter_language_pack import get_language, get_parser

from mrcis.extractors.context import ExtractionContext
from mrcis.models.extraction import ExtractionResult


@runtime_checkable
class ExtractorProtocol(Protocol):
    """Contract for language-specific code extractors.

    Extractors should implement the context-based extract_with_context() method.
    The legacy extract() method is supported for backward compatibility but
    will be deprecated in future versions.
    """

    def supports(self, file_path: Path) -> bool:
        """Check if this extractor supports the given file."""
        ...

    async def extract_with_context(self, context: ExtractionContext) -> ExtractionResult:
        """
        Extract entities and relations from a file using context object.

        This is the preferred method for new extractors. It provides a
        consistent interface and supports future extensibility.

        Args:
            context: ExtractionContext containing file path, IDs, and optional metadata.

        Returns:
            ExtractionResult containing all extracted entities and relations.
        """
        ...

    def get_supported_extensions(self) -> set[str]:
        """Return file extensions this extractor handles."""
        ...


def _collect_parse_errors(node: Node, file_path: Path) -> list[str]:
    """Walk the AST and collect ERROR/MISSING node locations."""
    errors: list[str] = []
    _walk_errors(node, file_path, errors)
    return errors


def _walk_errors(node: Node, file_path: Path, errors: list[str]) -> None:
    if node.type == "ERROR":
        start = node.start_point
        errors.append(
            f"Parse error in {file_path}:{start[0] + 1}:{start[1] + 1}"
            f" (len={node.end_byte - node.start_byte})"
        )
    elif node.is_missing:
        start = node.start_point
        errors.append(f"Missing '{node.type}' in {file_path}:{start[0] + 1}:{start[1] + 1}")
    else:
        for child in node.children:
            _walk_errors(child, file_path, errors)


class TreeSitterExtractor(ABC):
    """
    Base class for Tree-sitter based extractors.

    Provides:
    - Lazy parser initialization
    - Common AST traversal utilities
    - Error handling
    """

    def __init__(self) -> None:
        """Initialize extractor."""
        self._parser: Parser | None = None
        self._language: Language | None = None

    @abstractmethod
    def get_language_name(self) -> str:
        """Return tree-sitter language identifier."""
        ...

    @abstractmethod
    def get_supported_extensions(self) -> set[str]:
        """Return file extensions this extractor handles."""
        ...

    @abstractmethod
    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Language-specific extraction logic."""
        ...

    def supports(self, file_path: Path) -> bool:
        """Check if this extractor supports the file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def extract_with_context(self, context: ExtractionContext) -> ExtractionResult:
        """Parse file and extract entities using context object.

        This is the new context-based interface that all extractors should use.
        """
        # Lazy initialization
        if self._parser is None:
            self._init_parser()

        # At this point, _parser must be initialized
        if self._parser is None:
            raise RuntimeError("Parser not initialized after _init_parser()")

        # Read file (use pre-read bytes if available)
        source = context.source_bytes if context.source_bytes else context.file_path.read_bytes()

        # Parse
        tree = self._parser.parse(source)

        # Extract
        result = self._extract_from_tree(
            tree, source, context.file_path, context.file_id, context.repository_id
        )

        # Check for parse errors and collect their locations
        if tree.root_node.has_error:
            error_details = _collect_parse_errors(tree.root_node, context.file_path)
            result.parse_errors.extend(error_details)

        return result

    async def extract(
        self,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Parse file and extract entities (legacy signature).

        This method provides backward compatibility for existing code.
        New code should use extract_with_context() instead.
        """
        context = ExtractionContext(
            file_path=file_path,
            file_id=file_id,
            repository_id=repo_id,
        )
        return await self.extract_with_context(context)

    def _init_parser(self) -> None:
        """Initialize tree-sitter parser for this language."""
        lang_name = self.get_language_name()
        self._language = get_language(lang_name)  # type: ignore[arg-type]
        self._parser = get_parser(lang_name)  # type: ignore[arg-type]

    # =========================================================================
    # Utility Methods for Subclasses
    # =========================================================================

    def _node_text(self, node: Node, source: bytes) -> str:
        """Get text content of a node."""
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _find_child(self, node: Node, type_name: str) -> Node | None:
        """Find first child of type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _find_children(self, node: Node, type_name: str) -> list[Node]:
        """Find all direct children of type."""
        return [c for c in node.children if c.type == type_name]

    def _find_descendants(self, node: Node, type_name: str) -> list[Node]:
        """Recursively find all descendants of type."""
        results = []
        for child in node.children:
            if child.type == type_name:
                results.append(child)
            results.extend(self._find_descendants(child, type_name))
        return results

    def _get_docstring(self, body_node: Node | None, source: bytes) -> str | None:
        """Extract docstring from function/class body."""
        if not body_node or not body_node.children:
            return None

        first = body_node.children[0]

        # Python: can be either direct string or expression_statement -> string
        if first.type == "string":
            # Get the string_content child
            content_node = self._find_child(first, "string_content")
            if content_node:
                return self._node_text(content_node, source)
            # Fallback: strip quotes from full text
            text = self._node_text(first, source)
            return text.strip("\"'").strip()

        if first.type == "expression_statement":
            string_node = self._find_child(first, "string")
            if string_node:
                content_node = self._find_child(string_node, "string_content")
                if content_node:
                    return self._node_text(content_node, source)
                # Fallback: strip quotes from full text
                text = self._node_text(string_node, source)
                return text.strip("\"'").strip()

        return None

    def _get_source_line(self, node: Node, source: bytes) -> str:
        """Get the trimmed source line where a node starts."""
        lines = source.split(b"\n")
        line_idx = node.start_point[0]
        if 0 <= line_idx < len(lines):
            return lines[line_idx].decode("utf-8", errors="replace").strip()
        return ""

    def _build_qualified_name(
        self,
        name: str,
        parent: str | None = None,
        module: str | None = None,
    ) -> str:
        """Build fully qualified name."""
        parts = []
        if module:
            parts.append(module)
        if parent:
            parts.append(parent)
        parts.append(name)
        return ".".join(parts)
