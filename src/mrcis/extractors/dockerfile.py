"""Dockerfile-specific code extractor using Tree-sitter."""

from pathlib import Path
from uuid import UUID, uuid4

from tree_sitter import Node, Tree

from mrcis.extractors.base import TreeSitterExtractor
from mrcis.models.entities import (
    EntityType,
    FunctionEntity,
    ImportEntity,
    VariableEntity,
)
from mrcis.models.extraction import ExtractionResult


class DockerfileExtractor(TreeSitterExtractor):
    """
    Dockerfile-specific code extractor.

    Extracts:
    - Base images (FROM instructions as imports)
    - Environment variables (ENV, ARG as variables)
    - Exposed ports (EXPOSE as variables)
    - Entry points and commands (ENTRYPOINT, CMD as functions)
    - Build stages (multi-stage builds)
    """

    def get_language_name(self) -> str:
        """Return tree-sitter language name."""
        return "dockerfile"

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        # Dockerfiles typically have no extension or custom extensions like .dev, .prod
        return set()

    def supports(self, file_path: Path) -> bool:
        """Check if file is a Dockerfile."""
        name = file_path.name
        return name.startswith("Dockerfile") or name == "dockerfile"

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Extract entities from Dockerfile AST."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="dockerfile",
        )

        root = tree.root_node

        # Extract FROM instructions (base images)
        for node in self._find_descendants(root, "from_instruction"):
            self._extract_from(node, source, result, file_id, repo_id)

        # Extract ENV instructions
        for node in self._find_descendants(root, "env_instruction"):
            self._extract_env(node, source, result, file_id, repo_id)

        # Extract ARG instructions
        for node in self._find_descendants(root, "arg_instruction"):
            self._extract_arg(node, source, result, file_id, repo_id)

        # Extract EXPOSE instructions
        for node in self._find_descendants(root, "expose_instruction"):
            self._extract_expose(node, source, result, file_id, repo_id)

        # Extract ENTRYPOINT instructions
        for node in self._find_descendants(root, "entrypoint_instruction"):
            self._extract_entrypoint(node, source, result, file_id, repo_id)

        # Extract CMD instructions
        for node in self._find_descendants(root, "cmd_instruction"):
            self._extract_cmd(node, source, result, file_id, repo_id)

        return result

    def _extract_from(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract FROM instruction (base image)."""
        # Find the image specification
        image_spec = None
        image_alias = None

        for child in node.children:
            if child.type == "image_spec":
                image_spec = self._node_text(child, source)
            elif child.type == "image_alias":
                # Image alias is directly the alias text
                image_alias = self._node_text(child, source)

        if not image_spec:
            return

        # Store as ImportEntity (base images are like imports)
        imported_symbols = [image_alias] if image_alias else []

        result.imports.append(
            ImportEntity(
                id=uuid4(),
                name=image_spec,
                qualified_name=image_spec,
                entity_type=EntityType.IMPORT,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="dockerfile",
                source_module=image_spec,
                imported_symbols=imported_symbols,
                is_relative=False,
            )
        )

    def _extract_env(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract ENV instruction (environment variable)."""
        # ENV can have multiple pairs or single assignment
        for child in node.children:
            if child.type == "env_pair":
                self._extract_env_pair(child, source, result, file_id, repo_id, node)

    def _extract_env_pair(
        self,
        pair_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        parent_node: Node,
    ) -> None:
        """Extract a single ENV key=value pair."""
        key = None
        for child in pair_node.children:
            is_string = child.type in (
                "unquoted_string",
                "double_quoted_string",
                "single_quoted_string",
            )
            if is_string and key is None:
                # First string is the key
                key = self._node_text(child, source).strip("\"'")
                break

        if not key:
            return

        result.variables.append(
            VariableEntity(
                id=uuid4(),
                name=key,
                qualified_name=f"ENV.{key}",
                entity_type=EntityType.VARIABLE,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=parent_node.start_point[0] + 1,
                line_end=parent_node.end_point[0] + 1,
                language="dockerfile",
            )
        )

    def _extract_arg(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract ARG instruction (build argument)."""
        # Find the argument name
        arg_name = None
        for child in node.children:
            if child.type in ("unquoted_string", "double_quoted_string", "single_quoted_string"):
                text = self._node_text(child, source).strip("\"'")
                # ARG can be NAME or NAME=value
                arg_name = text.split("=")[0] if "=" in text else text
                break

        if not arg_name:
            return

        result.variables.append(
            VariableEntity(
                id=uuid4(),
                name=arg_name,
                qualified_name=f"ARG.{arg_name}",
                entity_type=EntityType.VARIABLE,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="dockerfile",
            )
        )

    def _extract_expose(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract EXPOSE instruction (port exposure)."""
        # Find the port number in expose_port node
        port = None
        for child in node.children:
            if child.type == "expose_port":
                text = self._node_text(child, source)
                # Port can be just number or number/protocol
                port = text.split("/")[0] if "/" in text else text
                break

        if not port:
            return

        result.variables.append(
            VariableEntity(
                id=uuid4(),
                name=f"port_{port}",
                qualified_name=f"EXPOSE.{port}",
                entity_type=EntityType.VARIABLE,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="dockerfile",
            )
        )

    def _extract_entrypoint(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract ENTRYPOINT instruction."""
        # Get the entrypoint command
        command_text = self._get_command_text(node, source)

        result.functions.append(
            FunctionEntity(
                id=uuid4(),
                name="entrypoint",
                qualified_name="ENTRYPOINT",
                entity_type=EntityType.FUNCTION,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="dockerfile",
                parameters=[],
                return_type=None,
                is_async=False,
                decorators=[],
                docstring=command_text,
            )
        )

    def _extract_cmd(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract CMD instruction."""
        # Get the command text
        command_text = self._get_command_text(node, source)

        result.functions.append(
            FunctionEntity(
                id=uuid4(),
                name="cmd",
                qualified_name="CMD",
                entity_type=EntityType.FUNCTION,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="dockerfile",
                parameters=[],
                return_type=None,
                is_async=False,
                decorators=[],
                docstring=command_text,
            )
        )

    def _get_command_text(self, node: Node, source: bytes) -> str:
        """Extract command text from ENTRYPOINT/CMD instruction."""
        # Try to find string array or shell form
        for child in node.children:
            if child.type == "string_array":
                # JSON array form: ["cmd", "arg1", "arg2"]
                parts = []
                for item in child.children:
                    if item.type in ("double_quoted_string", "single_quoted_string"):
                        parts.append(self._node_text(item, source).strip("\"'"))
                return " ".join(parts)
            elif child.type == "shell_command":
                # Shell form: cmd arg1 arg2
                return self._node_text(child, source)

        # Fallback: return entire node text minus the instruction keyword
        full_text = self._node_text(node, source)
        # Remove the instruction keyword (ENTRYPOINT or CMD)
        parts = full_text.split(maxsplit=1)
        return parts[1] if len(parts) > 1 else ""
