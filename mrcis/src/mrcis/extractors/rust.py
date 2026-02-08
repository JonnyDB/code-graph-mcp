"""Rust-specific code extractor using Tree-sitter."""

from pathlib import Path
from typing import ClassVar
from uuid import UUID, uuid4

from tree_sitter import Node, Tree

from mrcis.extractors.base import TreeSitterExtractor
from mrcis.models.entities import (
    ClassEntity,
    EntityType,
    FunctionEntity,
    ImportEntity,
    MethodEntity,
    ParameterEntity,
)
from mrcis.models.extraction import ExtractionResult
from mrcis.models.relations import PendingReference, RelationType


class RustExtractor(TreeSitterExtractor):
    """
    Rust-specific code extractor.

    Extracts:
    - use statements (imports)
    - mod declarations
    - struct, enum, trait definitions
    - impl blocks
    - Functions with lifetimes and generics
    """

    def get_language_name(self) -> str:
        """Return tree-sitter language name."""
        return "rust"

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".rs"}

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Extract entities from Rust AST."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="rust",
        )

        root = tree.root_node
        module_name = file_path.stem

        # Extract use statements
        self._extract_uses(root, source, result, file_id, repo_id)

        # Extract structs
        for node in self._find_descendants(root, "struct_item"):
            self._extract_struct(node, source, result, file_id, repo_id, module_name)

        # Extract enums
        for node in self._find_descendants(root, "enum_item"):
            self._extract_enum(node, source, result, file_id, repo_id, module_name)

        # Extract traits
        for node in self._find_descendants(root, "trait_item"):
            self._extract_trait(node, source, result, file_id, repo_id, module_name)

        # Extract functions
        for node in self._find_descendants(root, "function_item"):
            self._extract_function(node, source, result, file_id, repo_id, module_name)

        # Extract impl blocks
        for node in self._find_descendants(root, "impl_item"):
            self._extract_impl(node, source, result, file_id, repo_id, module_name)

        return result

    def _extract_uses(
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """
        Extract use statements.

        TODO: Known limitations (track for follow-up):
        - Aliased imports (use X as Y) incorrectly append alias to qualified name
        - Grouped imports (use foo::{bar, baz}) collapse into single import instead of multiple
        - These need refactoring to create separate ImportEntity per symbol and use alias field
        """
        for use_decl in self._find_descendants(root, "use_declaration"):
            # Extract path - can be scoped_identifier, identifier, use_wildcard, etc.
            path_parts: list[str] = []
            symbols: list[str] = []
            is_glob = False

            # Find the main identifier/scoped_identifier/use_wildcard
            for child in use_decl.children:
                if child.type in (
                    "scoped_identifier",
                    "identifier",
                    "use_wildcard",
                    "use_as_clause",
                    "use_list",
                ):
                    self._extract_use_path(child, source, path_parts, symbols)
                    if child.type == "use_wildcard":
                        is_glob = True

            if not path_parts:
                continue

            # Remove :: from path parts if accidentally included
            path_parts = [p for p in path_parts if p != "::"]

            # For imports like "use std::collections::HashMap",
            # the module should be "std::collections" (all but last)
            # and the symbol should be "HashMap" (last part)
            if len(path_parts) > 1 and not symbols and not is_glob:
                symbols = [path_parts[-1]]
                module = "::".join(path_parts[:-1])
            else:
                module = "::".join(path_parts)
                # If no explicit symbols, use last part of path
                if not symbols:
                    symbols = [path_parts[-1]] if path_parts else []

            # Determine qualified name based on whether it's a glob or has symbols
            if is_glob:
                qualified_name = module
            elif symbols:
                qualified_name = f"{module}::{symbols[0]}"
            else:
                qualified_name = module

            result.imports.append(
                ImportEntity(
                    id=uuid4(),
                    name=symbols[0] if symbols else module.split("::")[-1],
                    qualified_name=qualified_name,
                    entity_type=EntityType.IMPORT,
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path=result.file_path,
                    line_start=use_decl.start_point[0] + 1,
                    line_end=use_decl.end_point[0] + 1,
                    language="rust",
                    source_module=module,
                    imported_symbols=symbols,
                    is_relative=False,
                )
            )
            result.pending_references.append(
                PendingReference(
                    source_entity_id=result.imports[-1].id,
                    source_qualified_name=result.imports[-1].qualified_name,
                    source_repository_id=repo_id,
                    target_qualified_name=qualified_name,
                    relation_type=RelationType.IMPORTS,
                    line_number=use_decl.start_point[0] + 1,
                    context_snippet=self._get_source_line(use_decl, source),
                )
            )

    def _extract_use_path(  # noqa: PLR0912
        self, node: Node, source: bytes, path_parts: list[str], symbols: list[str]
    ) -> None:
        """Recursively extract use path and symbols."""
        if node.type == "identifier":
            path_parts.append(self._node_text(node, source))
        elif node.type == "scoped_identifier":
            # Recursively extract path in order
            for child in node.children:
                if child.type == "identifier":
                    path_parts.append(self._node_text(child, source))
                elif child.type == "scoped_identifier":
                    self._extract_use_path(child, source, path_parts, symbols)
        elif node.type == "use_wildcard":
            # For use_wildcard, extract the scoped_identifier first
            symbols.append("*")
            for child in node.children:
                if child.type in ("scoped_identifier", "identifier"):
                    self._extract_use_path(child, source, path_parts, symbols)
        elif node.type == "use_as_clause":
            # Handle aliased imports - extract the original name and the alias
            for child in node.children:
                if child.type == "identifier":
                    # This is the alias
                    symbols.append(self._node_text(child, source))
                elif child.type in ("scoped_identifier", "identifier"):
                    self._extract_use_path(child, source, path_parts, symbols)
        elif node.type == "use_list":
            # Handle use foo::{bar, baz}
            for child in node.children:
                if child.type in ("identifier", "scoped_identifier", "use_as_clause"):
                    self._extract_use_path(child, source, path_parts, symbols)
        elif node.type in ("crate", "self", "super"):
            path_parts.append(self._node_text(node, source))

    def _extract_struct(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a struct definition."""
        name_node = self._find_child(node, "type_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        class_entity = ClassEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="rust",
            base_classes=[],
            decorators=[],
        )
        result.classes.append(class_entity)

    def _extract_enum(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract an enum definition."""
        name_node = self._find_child(node, "type_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        # Store enums as classes (similar to structs)
        class_entity = ClassEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="rust",
            base_classes=[],
            decorators=[],
        )
        result.classes.append(class_entity)

    def _extract_trait(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a trait definition."""
        name_node = self._find_child(node, "type_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        # Store traits as abstract classes
        class_entity = ClassEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="rust",
            base_classes=[],
            decorators=[],
            is_abstract=True,  # Traits are abstract
        )
        result.classes.append(class_entity)

    def _extract_function(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a function definition."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        # Extract parameters
        params = self._extract_parameters(node, source)

        # Extract return type - look for type after "->"
        return_type = None
        found_arrow = False
        for child in node.children:
            if child.type == "->":
                found_arrow = True
            elif found_arrow and child.type in (
                "type_identifier",
                "primitive_type",
                "generic_type",
            ):
                return_type = self._node_text(child, source)
                break

        func_entity = FunctionEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.FUNCTION,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="rust",
            parameters=params,
            return_type=return_type,
            is_async=any(c.type == "async" for c in node.children),
            decorators=[],
        )
        result.functions.append(func_entity)

        body = self._find_child(node, "block")
        if body:
            self._extract_calls(body, source, func_entity, result, repo_id, parent_class=None)

    def _extract_impl(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract methods from impl blocks."""
        # Get the type being implemented
        type_node = self._find_child(node, "type_identifier")
        if not type_node:
            return

        impl_type = self._node_text(type_node, source)

        # Extract methods from the impl block
        declaration_list = self._find_child(node, "declaration_list")
        if not declaration_list:
            return

        for func in self._find_children(declaration_list, "function_item"):
            self._extract_method(func, source, result, file_id, repo_id, module_name, impl_type)

    def _extract_method(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        parent_class: str,
    ) -> None:
        """Extract a method from an impl block."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, parent=parent_class, module=module_name)

        # Extract parameters
        params = self._extract_parameters(node, source)

        # Extract return type - look for type after "->"
        return_type = None
        found_arrow = False
        for child in node.children:
            if child.type == "->":
                found_arrow = True
            elif found_arrow and child.type in (
                "type_identifier",
                "primitive_type",
                "generic_type",
            ):
                return_type = self._node_text(child, source)
                break

        method_entity = MethodEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.METHOD,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="rust",
            parameters=params,
            return_type=return_type,
            is_async=any(c.type == "async" for c in node.children),
            is_static=not any(p.name in ("self", "&self", "&mut self") for p in params),
            parent_class=parent_class,
        )
        result.methods.append(method_entity)

        body = self._find_child(node, "block")
        if body:
            self._extract_calls(body, source, method_entity, result, repo_id, parent_class)

    def _extract_parameters(self, func_node: Node, source: bytes) -> list[ParameterEntity]:
        """Extract function parameters."""
        params: list[ParameterEntity] = []
        params_node = self._find_child(func_node, "parameters")
        if not params_node:
            return params

        for child in params_node.children:
            if child.type in ("parameter", "self_parameter"):
                if child.type == "self_parameter":
                    # Extract self parameter
                    params.append(
                        ParameterEntity(
                            name=self._node_text(child, source),
                            type_annotation=None,
                        )
                    )
                else:
                    # Extract regular parameter (pattern: type)
                    pattern = self._find_child(child, "identifier")
                    # Type can be type_identifier, primitive_type, or other type nodes
                    type_node = None
                    for grandchild in child.children:
                        if grandchild.type in (
                            "type_identifier",
                            "primitive_type",
                            "generic_type",
                            "reference_type",
                        ):
                            type_node = grandchild
                            break

                    if pattern:
                        params.append(
                            ParameterEntity(
                                name=self._node_text(pattern, source),
                                type_annotation=(
                                    self._node_text(type_node, source) if type_node else None
                                ),
                            )
                        )

        return params

    # =========================================================================
    # Call-Site Extraction
    # =========================================================================

    _SKIP_NAMES: ClassVar[set[str]] = {
        "println",
        "print",
        "format",
        "eprintln",
        "vec",
        "todo",
        "unimplemented",
        "panic",
        "assert",
        "assert_eq",
        "assert_ne",
        "dbg",
        "cfg",
    }

    def _extract_calls(
        self,
        body_node: Node,
        source: bytes,
        entity: FunctionEntity | MethodEntity,
        result: ExtractionResult,
        repo_id: UUID,
        parent_class: str | None,
    ) -> None:
        """Extract call sites from a Rust function/method body."""
        seen: set[str] = set()

        for call_node in self._find_descendants(body_node, "call_expression"):
            # Skip if parent is a macro_invocation
            if call_node.parent and call_node.parent.type == "macro_invocation":
                continue

            callee = self._resolve_callee(call_node, source, parent_class)
            if not callee:
                continue

            simple = callee.rsplit(".", 1)[-1].rsplit("::", 1)[-1]
            if simple in self._SKIP_NAMES or callee in seen:
                continue
            seen.add(callee)

            # Extract receiver expression (object/module before the method/function)
            receiver_expr = self._extract_receiver_expr(call_node, source, parent_class)

            entity.calls.append(callee)
            result.pending_references.append(
                PendingReference(
                    source_entity_id=entity.id,
                    source_qualified_name=entity.qualified_name,
                    source_repository_id=repo_id,
                    target_qualified_name=callee,
                    relation_type=RelationType.CALLS,
                    line_number=call_node.start_point[0] + 1,
                    context_snippet=self._get_source_line(call_node, source),
                    receiver_expr=receiver_expr,
                )
            )

    def _resolve_callee(
        self,
        call_node: Node,
        source: bytes,
        parent_class: str | None,
    ) -> str | None:
        """Resolve the callee name from a Rust call node."""
        if not call_node.children:
            return None

        func_child = call_node.children[0]

        if func_child.type == "identifier":
            return self._node_text(func_child, source)

        if func_child.type == "field_expression":
            full_text = self._node_text(func_child, source)
            parts = full_text.split(".")
            if parts[0] == "self" and parent_class:
                parts[0] = parent_class
            return ".".join(parts)

        if func_child.type == "scoped_identifier":
            return self._node_text(func_child, source)

        return None

    def _extract_receiver_expr(
        self,
        call_node: Node,
        source: bytes,
        parent_class: str | None,
    ) -> str | None:
        """
        Extract the receiver expression from a call node.

        Returns the object/module part before the last method/function name.

        Examples:
        - writer.write() -> "writer"
        - ctx.redis.get() -> "ctx.redis"
        - do_work() -> None (direct call)
        - self.helper() -> None (already resolved to ClassName.method)
        """
        if not call_node.children:
            return None

        func_child = call_node.children[0]

        # Direct identifier call (e.g., func()) has no receiver
        if func_child.type == "identifier":
            return None

        # Field expression (e.g., obj.method())
        if func_child.type == "field_expression":
            full_text = self._node_text(func_child, source)
            parts = full_text.split(".")

            # self calls are already resolved to ClassName.method, no receiver needed
            if parts[0] == "self" and parent_class:
                return None

            # Return all parts except the last (method name)
            if len(parts) > 1:
                return ".".join(parts[:-1])

        # Scoped identifier (e.g., std::io::read) has no receiver
        if func_child.type == "scoped_identifier":
            return None

        return None
