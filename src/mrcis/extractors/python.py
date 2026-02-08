"""Python-specific code extractor using Tree-sitter."""

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


class PythonExtractor(TreeSitterExtractor):
    """
    Python-specific code extractor.

    Extracts:
    - Classes (with inheritance, decorators, methods)
    - Functions (with parameters, return types)
    - Imports (import x, from x import y)
    - Module-level variables/constants
    """

    def get_language_name(self) -> str:
        """Return tree-sitter language name."""
        return "python"

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".py", ".pyi"}

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Extract entities from Python AST."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="python",
        )

        root = tree.root_node

        # Derive module name from file path
        module_name = file_path.stem if file_path.stem != "__init__" else file_path.parent.name

        # Extract imports first
        self._extract_imports(root, source, result, file_id, repo_id)

        # Extract classes
        for class_node in self._find_descendants(root, "class_definition"):
            self._extract_class(class_node, source, result, file_id, repo_id, module_name)

        # Extract top-level functions
        for child in root.children:
            func_node = None
            if child.type == "function_definition":
                func_node = child
            elif child.type == "decorated_definition":
                # Find the function_definition inside decorated_definition
                func_node = self._find_child(child, "function_definition")

            if func_node:
                self._extract_function(
                    func_node, source, result, file_id, repo_id, module_name, parent_class=None
                )

        return result

    def _get_full_source(self, node: Node, source: bytes) -> str:
        """Get source text for a node, including decorators if present."""
        if node.parent and node.parent.type == "decorated_definition":
            return self._node_text(node.parent, source)
        return self._node_text(node, source)

    def _extract_imports(  # noqa: PLR0912
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract import statements."""
        # Handle simple imports: import x, y
        for imp in self._find_children(root, "import_statement"):
            names = self._find_descendants(imp, "dotted_name")
            for name_node in names:
                module = self._node_text(name_node, source)
                result.imports.append(
                    ImportEntity(
                        id=uuid4(),
                        name=module.split(".")[-1],
                        qualified_name=module,
                        entity_type=EntityType.IMPORT,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=result.file_path,
                        line_start=imp.start_point[0] + 1,
                        line_end=imp.end_point[0] + 1,
                        language="python",
                        source_module=module,
                        imported_symbols=[],
                        is_relative=False,
                    )
                )
                # Create pending reference for import resolution
                result.pending_references.append(
                    PendingReference(
                        source_entity_id=result.imports[-1].id,
                        source_qualified_name=result.imports[-1].qualified_name,
                        source_repository_id=repo_id,
                        target_qualified_name=module,
                        relation_type=RelationType.IMPORTS,
                        line_number=imp.start_point[0] + 1,
                        context_snippet=self._get_source_line(imp, source),
                    )
                )

        # Handle from imports: from x import y, z
        for imp in self._find_children(root, "import_from_statement"):
            # Check for relative import first
            relative_level = 0
            relative_import_node = self._find_child(imp, "relative_import")
            if relative_import_node:
                # Count dots in import_prefix
                for child in relative_import_node.children:
                    if child.type == "import_prefix":
                        for dot in child.children:
                            if dot.type == ".":
                                relative_level += 1

            # Get module name
            # For relative imports, module is inside relative_import node
            # For absolute imports, module is a direct child dotted_name
            module_node = None
            if relative_import_node:
                # Look for dotted_name inside relative_import
                module_node = self._find_child(relative_import_node, "dotted_name")
            else:
                # For absolute imports, first dotted_name is the module
                all_dotted = self._find_children(imp, "dotted_name")
                module_node = all_dotted[0] if all_dotted else None
            module = self._node_text(module_node, source) if module_node else ""

            # Get imported names (exclude the module name if present)
            # Collect direct children only to avoid duplicating names from aliased_import
            symbols = []
            for child in imp.children:
                if child.type == "dotted_name" and child != module_node:
                    symbols.append(self._node_text(child, source))
                elif child.type == "aliased_import":
                    # For aliased imports, get the original name
                    name_child = self._find_child(child, "dotted_name")
                    if name_child:
                        symbols.append(self._node_text(name_child, source))

            # Check for wildcard
            is_wildcard = any(c.type == "wildcard_import" for c in imp.children)
            if is_wildcard:
                symbols = ["*"]

            # Handle qualified_name for relative imports
            # For "from . import x", module is empty, so use first symbol
            # For "from .module import x", use module.symbol
            if symbols and module:
                qualified_name = f"{module}.{symbols[0]}"
            elif symbols:
                # Relative import with no module: "from . import x"
                qualified_name = symbols[0]
            else:
                # No symbols imported (shouldn't happen in valid Python)
                qualified_name = module

            result.imports.append(
                ImportEntity(
                    id=uuid4(),
                    name=symbols[0] if symbols else module,
                    qualified_name=qualified_name,
                    entity_type=EntityType.IMPORT,
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path=result.file_path,
                    line_start=imp.start_point[0] + 1,
                    line_end=imp.end_point[0] + 1,
                    language="python",
                    source_module=module,
                    imported_symbols=symbols,
                    is_wildcard=is_wildcard,
                    is_relative=relative_level > 0,
                    relative_level=relative_level,
                )
            )

            # Create pending references for each imported symbol
            import_entity = result.imports[-1]
            for sym in symbols:
                if sym == "*":
                    continue
                target = f"{module}.{sym}" if module else sym
                result.pending_references.append(
                    PendingReference(
                        source_entity_id=import_entity.id,
                        source_qualified_name=import_entity.qualified_name,
                        source_repository_id=repo_id,
                        target_qualified_name=target,
                        relation_type=RelationType.IMPORTS,
                        line_number=imp.start_point[0] + 1,
                        context_snippet=self._get_source_line(imp, source),
                    )
                )

    def _extract_class(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a class definition."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        # Get base classes
        bases = []
        args_node = self._find_child(node, "argument_list")
        if args_node:
            for arg in args_node.children:
                if arg.type in ("identifier", "attribute"):
                    bases.append(self._node_text(arg, source))

        # Get decorators
        decorators = self._get_decorators(node, source)

        # Get body and docstring
        body = self._find_child(node, "block")
        docstring = self._get_docstring(body, source) if body else None

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
            language="python",
            base_classes=bases,
            decorators=decorators,
            docstring=docstring,
            source_text=self._get_full_source(node, source),
            is_abstract="ABC" in bases or any("abstractmethod" in d for d in decorators),
            is_dataclass=any("dataclass" in d for d in decorators),
        )
        result.classes.append(class_entity)

        # Queue inheritance for resolution
        for base in bases:
            result.pending_references.append(
                PendingReference(
                    source_entity_id=class_entity.id,
                    source_qualified_name=qualified_name,
                    source_repository_id=repo_id,
                    target_qualified_name=base,
                    relation_type=RelationType.EXTENDS,
                    line_number=node.start_point[0] + 1,
                    context_snippet=self._get_source_line(node, source),
                )
            )

        # Extract methods
        if body:
            for child in body.children:
                # Handle both direct function_definition and decorated_definition
                method_node = None
                if child.type == "function_definition":
                    method_node = child
                elif child.type == "decorated_definition":
                    # Find the function_definition inside decorated_definition
                    method_node = self._find_child(child, "function_definition")

                if method_node:
                    self._extract_function(
                        method_node,
                        source,
                        result,
                        file_id,
                        repo_id,
                        module_name,
                        parent_class=qualified_name,
                    )

                    # Track method names
                    method_name_node = self._find_child(method_node, "identifier")
                    if method_name_node:
                        method_name = self._node_text(method_name_node, source)
                        class_entity.method_names.append(method_name)

    def _get_decorators(self, node: Node, source: bytes) -> list[str]:
        """Get decorators for a function/class."""
        decorators = []

        # If parent is decorated_definition, decorators are siblings in that parent
        if node.parent and node.parent.type == "decorated_definition":
            for sibling in node.parent.children:
                if sibling == node:
                    break
                if sibling.type == "decorator":
                    # Get just the decorator name (skip @)
                    decorator_text = self._node_text(sibling, source)
                    decorators.append(decorator_text)
        elif node.parent:
            # Look for decorator siblings before the definition
            for sibling in node.parent.children:
                if sibling == node:
                    break
                if sibling.type == "decorator":
                    decorator_text = self._node_text(sibling, source)
                    decorators.append(decorator_text)

        return decorators

    def _extract_function(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        parent_class: str | None,
    ) -> None:
        """Extract a function or method."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(
            name, parent=parent_class, module=module_name if parent_class is None else None
        )

        # Get parameters
        params = self._extract_parameters(node, source)

        # Get return type
        return_type = None
        return_node = self._find_child(node, "type")
        if return_node:
            return_type = self._node_text(return_node, source)

        # Get decorators
        decorators = self._get_decorators(node, source)

        # Get body and docstring
        body = self._find_child(node, "block")
        docstring = self._get_docstring(body, source) if body else None

        # Build signature
        param_str = ", ".join(
            f"{p.name}: {p.type_annotation}" if p.type_annotation else p.name for p in params
        )
        signature = f"def {name}({param_str})"
        if return_type:
            signature += f" -> {return_type}"

        # Check if async (async is a direct child of function_definition)
        is_async = any(c.type == "async" for c in node.children)

        # Determine if method
        is_method = parent_class is not None

        # Extract call sites from function body
        entity: FunctionEntity | MethodEntity

        if is_method and parent_class is not None:
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
                language="python",
                parameters=params,
                return_type=return_type,
                is_async=is_async,
                decorators=decorators,
                docstring=docstring,
                source_text=self._get_full_source(node, source),
                signature=signature,
                parent_class=parent_class,
                is_static=any("staticmethod" in d for d in decorators),
                is_classmethod=any("classmethod" in d for d in decorators),
                is_property=any("property" in d for d in decorators),
                is_constructor=name == "__init__",
            )
            result.methods.append(method_entity)
            entity = method_entity
        else:
            function_entity = FunctionEntity(
                id=uuid4(),
                name=name,
                qualified_name=qualified_name,
                entity_type=EntityType.FUNCTION,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                language="python",
                parameters=params,
                return_type=return_type,
                is_async=is_async,
                decorators=decorators,
                docstring=docstring,
                source_text=self._get_full_source(node, source),
                signature=signature,
            )
            result.functions.append(function_entity)
            entity = function_entity

        if body:
            self._extract_calls(body, source, entity, result, repo_id, parent_class)

    def _extract_parameters(self, func_node: Node, source: bytes) -> list[ParameterEntity]:
        """Extract function parameters."""
        params: list[ParameterEntity] = []
        params_node = self._find_child(func_node, "parameters")
        if not params_node:
            return params

        for child in params_node.children:
            if child.type in (
                "identifier",
                "typed_parameter",
                "default_parameter",
                "typed_default_parameter",
            ):
                param = self._parse_parameter(child, source)
                if param and param.name not in ("self", "cls"):
                    params.append(param)

        return params

    def _parse_parameter(self, node: Node, source: bytes) -> ParameterEntity | None:
        """Parse a single parameter node."""
        if node.type == "identifier":
            return ParameterEntity(name=self._node_text(node, source))

        if node.type == "typed_parameter":
            name_node = self._find_child(node, "identifier")
            type_node = self._find_child(node, "type")
            return ParameterEntity(
                name=self._node_text(name_node, source) if name_node else "",
                type_annotation=self._node_text(type_node, source) if type_node else None,
            )

        if node.type == "default_parameter":
            name_node = self._find_child(node, "identifier")
            return ParameterEntity(
                name=self._node_text(name_node, source) if name_node else "",
                is_optional=True,
            )

        if node.type == "typed_default_parameter":
            name_node = self._find_child(node, "identifier")
            type_node = self._find_child(node, "type")
            return ParameterEntity(
                name=self._node_text(name_node, source) if name_node else "",
                type_annotation=self._node_text(type_node, source) if type_node else None,
                is_optional=True,
            )

        return None

    # =========================================================================
    # Call-Site Extraction
    # =========================================================================

    _SKIP_NAMES: ClassVar[set[str]] = {
        "print",
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "range",
        "enumerate",
        "zip",
        "map",
        "filter",
        "sorted",
        "reversed",
        "min",
        "max",
        "sum",
        "any",
        "all",
        "abs",
        "round",
        "isinstance",
        "issubclass",
        "hasattr",
        "getattr",
        "setattr",
        "delattr",
        "type",
        "id",
        "repr",
        "hash",
        "super",
        "next",
        "iter",
        "open",
        "input",
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
        """Extract call sites from a Python function/method body."""
        seen: set[str] = set()

        for call_node in self._find_descendants(body_node, "call"):
            callee = self._resolve_callee(call_node, source, parent_class)
            if not callee:
                continue

            simple = callee.rsplit(".", 1)[-1]
            if simple in self._SKIP_NAMES or callee in seen:
                continue
            seen.add(callee)

            # Uppercase-first heuristic for instantiation
            relation_type = RelationType.INSTANTIATES if simple[0].isupper() else RelationType.CALLS

            # Extract receiver expression (object/module before the method/function)
            receiver_expr = self._extract_receiver_expr(call_node, source, parent_class)

            entity.calls.append(callee)
            result.pending_references.append(
                PendingReference(
                    source_entity_id=entity.id,
                    source_qualified_name=entity.qualified_name,
                    source_repository_id=repo_id,
                    target_qualified_name=callee,
                    relation_type=relation_type,
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
        """Resolve the callee name from a Python call node."""
        if not call_node.children:
            return None

        func_child = call_node.children[0]

        if func_child.type == "identifier":
            return self._node_text(func_child, source)

        if func_child.type == "attribute":
            full_text = self._node_text(func_child, source)
            parts = full_text.split(".")
            if parts[0] in ("self", "cls") and parent_class:
                # Replace self/cls with class simple name
                class_name = parent_class.rsplit(".", 1)[-1]
                parts[0] = class_name
            return ".".join(parts)

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
        - chart_writer.get() -> "chart_writer"
        - ctx.redis.get() -> "ctx.redis"
        - os.path.join() -> "os.path"
        - process_data() -> None (direct call)
        - self.helper() -> None (already resolved to ClassName.method)
        """
        if not call_node.children:
            return None

        func_child = call_node.children[0]

        # Direct identifier call (e.g., func()) has no receiver
        if func_child.type == "identifier":
            return None

        # Attribute access (e.g., obj.method() or module.func())
        if func_child.type == "attribute":
            full_text = self._node_text(func_child, source)
            parts = full_text.split(".")

            # self/cls calls are already resolved to ClassName.method, no receiver needed
            if parts[0] in ("self", "cls") and parent_class:
                return None

            # Return all parts except the last (method/function name)
            if len(parts) > 1:
                return ".".join(parts[:-1])

        return None
