"""Go-specific code extractor using Tree-sitter."""

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


class GoExtractor(TreeSitterExtractor):
    """Go-specific code extractor."""

    def get_language_name(self) -> str:
        return "go"

    def get_supported_extensions(self) -> set[str]:
        return {".go"}

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="go",
        )

        root = tree.root_node
        module_name = file_path.stem

        # Extract package name
        pkg_node = self._find_child(root, "package_clause")
        if pkg_node:
            pkg_id = self._find_child(pkg_node, "package_identifier")
            if pkg_id:
                module_name = self._node_text(pkg_id, source)

        # Extract imports
        self._extract_imports(root, source, result, file_id, repo_id)

        # Extract type declarations (structs, interfaces)
        for decl in self._find_descendants(root, "type_declaration"):
            self._extract_type(decl, source, result, file_id, repo_id, module_name)

        # Extract functions
        for func in self._find_descendants(root, "function_declaration"):
            self._extract_function(func, source, result, file_id, repo_id, module_name)

        # Extract methods (functions with receivers)
        for method in self._find_descendants(root, "method_declaration"):
            self._extract_method(method, source, result, file_id, repo_id, module_name)

        return result

    def _extract_imports(
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract import statements."""
        for imp_decl in self._find_descendants(root, "import_declaration"):
            # Single import
            import_spec = self._find_child(imp_decl, "import_spec")
            if import_spec:
                self._add_import(import_spec, source, result, file_id, repo_id)

            # Import block
            import_list = self._find_child(imp_decl, "import_spec_list")
            if import_list:
                for spec in self._find_children(import_list, "import_spec"):
                    self._add_import(spec, source, result, file_id, repo_id)

    def _add_import(
        self,
        spec: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Add a single import from spec."""
        path_node = self._find_child(spec, "interpreted_string_literal")
        if not path_node:
            return

        module = self._node_text(path_node, source).strip('"')
        name = module.split("/")[-1]

        # Check for alias
        alias_node = self._find_child(spec, "package_identifier")
        if alias_node:
            name = self._node_text(alias_node, source)

        result.imports.append(
            ImportEntity(
                id=uuid4(),
                name=name,
                qualified_name=module,
                entity_type=EntityType.IMPORT,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=spec.start_point[0] + 1,
                line_end=spec.end_point[0] + 1,
                language="go",
                source_module=module,
                imported_symbols=[name],
                is_relative=False,
            )
        )
        result.pending_references.append(
            PendingReference(
                source_entity_id=result.imports[-1].id,
                source_qualified_name=result.imports[-1].qualified_name,
                source_repository_id=repo_id,
                target_qualified_name=module,
                relation_type=RelationType.IMPORTS,
                line_number=spec.start_point[0] + 1,
                context_snippet=self._get_source_line(spec, source),
            )
        )

    def _extract_type(
        self,
        decl: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract struct or interface type."""
        for spec in self._find_children(decl, "type_spec"):
            name_node = self._find_child(spec, "type_identifier")
            if not name_node:
                continue

            name = self._node_text(name_node, source)
            qualified_name = self._build_qualified_name(name, module=module_name)

            # Determine type (struct vs interface)
            self._find_child(spec, "struct_type")
            interface_type = self._find_child(spec, "interface_type")

            class_entity = ClassEntity(
                id=uuid4(),
                name=name,
                qualified_name=qualified_name,
                entity_type=EntityType.CLASS,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=spec.start_point[0] + 1,
                line_end=spec.end_point[0] + 1,
                language="go",
                base_classes=[],
                decorators=[],
                is_abstract=interface_type is not None,
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
        """Extract a function declaration."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        params = self._extract_parameters(node, source)
        return_type = self._extract_return_type(node, source)

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
            language="go",
            parameters=params,
            return_type=return_type,
            is_async=False,  # Go doesn't have async keyword
            decorators=[],
        )
        result.functions.append(func_entity)

        body = self._find_child(node, "block")
        if body:
            self._extract_calls(body, source, func_entity, result, repo_id)

    def _extract_method(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a method (function with receiver)."""
        name_node = self._find_child(node, "field_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)

        # Get receiver type (parent class)
        receiver = self._find_child(node, "parameter_list")
        parent_class = ""
        if receiver and receiver.children:
            param_decl = self._find_child(receiver, "parameter_declaration")
            if param_decl:
                type_node = param_decl.children[-1] if param_decl.children else None
                if type_node:
                    parent_class = self._node_text(type_node, source).strip("*")

        qualified_name = self._build_qualified_name(name, parent=parent_class, module=module_name)

        params = self._extract_parameters(node, source, skip_first=True)
        return_type = self._extract_return_type(node, source)

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
            language="go",
            parameters=params,
            return_type=return_type,
            is_async=False,
            parent_class=parent_class,
            is_static=False,
        )
        result.methods.append(method_entity)

        body = self._find_child(node, "block")
        if body:
            self._extract_calls(body, source, method_entity, result, repo_id)

    def _extract_parameters(
        self, func_node: Node, source: bytes, skip_first: bool = False
    ) -> list[ParameterEntity]:
        """Extract function parameters."""
        params: list[ParameterEntity] = []
        param_lists = self._find_children(func_node, "parameter_list")

        # For methods, first param list is receiver, second is parameters
        if skip_first and len(param_lists) >= 2:
            param_list = param_lists[1]
        elif param_lists:
            param_list = param_lists[0]
        else:
            return params

        for decl in self._find_children(param_list, "parameter_declaration"):
            names = self._find_children(decl, "identifier")
            type_node = decl.children[-1] if decl.children else None
            type_str = self._node_text(type_node, source) if type_node else None

            for name_node in names:
                params.append(
                    ParameterEntity(
                        name=self._node_text(name_node, source),
                        type_annotation=type_str,
                    )
                )

        return params

    def _extract_return_type(self, func_node: Node, source: bytes) -> str | None:
        """Extract function return type."""
        result_node = None
        for child in func_node.children:
            is_return_type = child.type in (
                "type_identifier",
                "pointer_type",
                "slice_type",
                "parameter_list",
            )
            is_after_params = child.prev_sibling and child.prev_sibling.type == "parameter_list"
            if is_return_type and is_after_params:
                result_node = child
                break

        if result_node:
            return self._node_text(result_node, source)
        return None

    # =========================================================================
    # Call-Site Extraction
    # =========================================================================

    _SKIP_NAMES: ClassVar[set[str]] = {
        "len",
        "cap",
        "make",
        "new",
        "append",
        "copy",
        "delete",
        "close",
        "panic",
        "recover",
    }

    def _extract_calls(
        self,
        body_node: Node,
        source: bytes,
        entity: FunctionEntity | MethodEntity,
        result: ExtractionResult,
        repo_id: UUID,
    ) -> None:
        """Extract call sites from a Go function/method body."""
        seen: set[str] = set()

        for call_node in self._find_descendants(body_node, "call_expression"):
            callee = self._resolve_callee(call_node, source)
            if not callee:
                continue

            simple = callee.rsplit(".", 1)[-1]
            if simple in self._SKIP_NAMES or callee in seen:
                continue
            seen.add(callee)

            # Extract receiver expression (object/module before the method/function)
            receiver_expr = self._extract_receiver_expr(call_node, source, None)

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
    ) -> str | None:
        """Resolve the callee name from a Go call node."""
        if not call_node.children:
            return None

        func_child = call_node.children[0]

        if func_child.type == "identifier":
            return self._node_text(func_child, source)

        if func_child.type == "selector_expression":
            return self._node_text(func_child, source)

        return None

    def _extract_receiver_expr(
        self,
        call_node: Node,
        source: bytes,
        parent_class: str | None,  # noqa: ARG002 - Go has no self equivalent
    ) -> str | None:
        """
        Extract the receiver expression from a call node.

        Returns the object/module part before the last method/function name.

        Examples:
        - writer.Write() -> "writer"
        - ctx.redis.Get() -> "ctx.redis"
        - fmt.Println() -> "fmt"
        - DoWork() -> None (direct call)

        Note: Go has no 'self' equivalent, so parent_class is unused.
        """
        if not call_node.children:
            return None

        func_child = call_node.children[0]

        # Direct identifier call (e.g., func()) has no receiver
        if func_child.type == "identifier":
            return None

        # Selector expression (e.g., obj.method() or pkg.func())
        if func_child.type == "selector_expression":
            full_text = self._node_text(func_child, source)
            parts = full_text.split(".")

            # Return all parts except the last (method/function name)
            if len(parts) > 1:
                return ".".join(parts[:-1])

        return None
