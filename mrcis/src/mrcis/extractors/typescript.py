"""TypeScript-specific code extractor using Tree-sitter."""

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
    VariableEntity,
)
from mrcis.models.extraction import ExtractionResult
from mrcis.models.relations import PendingReference, RelationType


class TypeScriptExtractor(TreeSitterExtractor):
    """
    TypeScript-specific code extractor.

    Extracts:
    - Classes and interfaces
    - Functions (regular, arrow, async)
    - Imports (ES modules)
    - Type aliases
    - Variables/constants
    """

    _SKIP_NAMES: ClassVar[set[str]] = {
        "parseInt",
        "parseFloat",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "require",
        "alert",
        "console.log",
        "console.error",
        "console.warn",
        "console.info",
        "console.debug",
    }

    def get_language_name(self) -> str:
        """Return tree-sitter language name."""
        return "typescript"

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".ts", ".tsx"}

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Extract entities from TypeScript AST."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="typescript",
        )

        root = tree.root_node
        module_name = file_path.stem

        # Extract imports
        self._extract_imports(root, source, result, file_id, repo_id)

        # Extract classes and interfaces
        for node in self._find_descendants(root, "class_declaration"):
            self._extract_class(node, source, result, file_id, repo_id, module_name)

        for node in self._find_descendants(root, "interface_declaration"):
            self._extract_interface(node, source, result, file_id, repo_id, module_name)

        # Extract functions
        for node in self._find_descendants(root, "function_declaration"):
            self._extract_function(node, source, result, file_id, repo_id, module_name)

        # Extract arrow functions assigned to variables
        for node in self._find_descendants(root, "lexical_declaration"):
            self._extract_variable_declarations(node, source, result, file_id, repo_id, module_name)

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
        for imp in self._find_descendants(root, "import_statement"):
            # Get source module from string
            source_node = self._find_child(imp, "string")
            if not source_node:
                continue
            module = self._node_text(source_node, source).strip("'\"")

            # Get imported symbols
            symbols = []
            import_clause = self._find_child(imp, "import_clause")
            if import_clause:
                # Default import
                default_id = self._find_child(import_clause, "identifier")
                if default_id:
                    symbols.append(self._node_text(default_id, source))
                # Named imports
                named = self._find_child(import_clause, "named_imports")
                if named:
                    for spec in self._find_descendants(named, "import_specifier"):
                        name_node = self._find_child(spec, "identifier")
                        if name_node:
                            symbols.append(self._node_text(name_node, source))

            result.imports.append(
                ImportEntity(
                    id=uuid4(),
                    name=symbols[0] if symbols else module.split("/")[-1],
                    qualified_name=f"{module}.{symbols[0]}" if symbols else module,
                    entity_type=EntityType.IMPORT,
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path=result.file_path,
                    line_start=imp.start_point[0] + 1,
                    line_end=imp.end_point[0] + 1,
                    language="typescript",
                    source_module=module,
                    imported_symbols=symbols,
                    is_relative=module.startswith("."),
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
        """Extract a class declaration."""
        name_node = self._find_child(node, "type_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        # Get base classes
        bases = []
        extends = self._find_child(node, "class_heritage")
        if extends:
            for clause in extends.children:
                if clause.type == "extends_clause":
                    type_node = self._find_child(clause, "type_identifier")
                    if type_node:
                        bases.append(self._node_text(type_node, source))

        # Get body
        body = self._find_child(node, "class_body")
        docstring = None  # TSDoc extraction would go here

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
            language="typescript",
            base_classes=bases,
            decorators=[],
            docstring=docstring,
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
            for method in self._find_children(body, "method_definition"):
                self._extract_method(
                    method, source, result, file_id, repo_id, module_name, qualified_name
                )

    def _extract_interface(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract an interface declaration."""
        name_node = self._find_child(node, "type_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)

        # Store as ClassEntity with is_abstract=True to indicate interface
        interface_entity = ClassEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="typescript",
            base_classes=[],
            decorators=[],
            is_abstract=True,  # Interfaces are abstract by nature
        )
        result.classes.append(interface_entity)

    def _extract_function(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        parent_class: str | None = None,
    ) -> None:
        """Extract a function declaration."""
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
        type_annotation = self._find_child(node, "type_annotation")
        if type_annotation:
            type_node = type_annotation.children[-1] if type_annotation.children else None
            if type_node:
                return_type = self._node_text(type_node, source)

        # Check if async
        is_async = any(c.type == "async" for c in node.children)

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
            language="typescript",
            parameters=params,
            return_type=return_type,
            is_async=is_async,
            decorators=[],
        )
        result.functions.append(func_entity)

        body = self._find_child(node, "statement_block")
        if body:
            self._extract_calls(body, source, func_entity, result, repo_id, parent_class)

    def _extract_method(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        _module_name: str,
        parent_class: str,
    ) -> None:
        """Extract a method from a class."""
        name_node = self._find_child(node, "property_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, parent=parent_class)

        # Get parameters
        params = self._extract_parameters(node, source)

        # Get return type
        return_type = None
        type_annotation = self._find_child(node, "type_annotation")
        if type_annotation:
            type_node = type_annotation.children[-1] if type_annotation.children else None
            if type_node:
                return_type = self._node_text(type_node, source)

        # Check modifiers
        is_async = any(c.type == "async" for c in node.children)
        is_static = any(c.type == "static" for c in node.children)

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
            language="typescript",
            parameters=params,
            return_type=return_type,
            is_async=is_async,
            is_static=is_static,
            parent_class=parent_class,
            is_constructor=name == "constructor",
        )
        result.methods.append(method_entity)

        body = self._find_child(node, "statement_block")
        if body:
            self._extract_calls(body, source, method_entity, result, repo_id, parent_class)

    def _extract_parameters(self, func_node: Node, source: bytes) -> list[ParameterEntity]:
        """Extract function parameters."""
        params: list[ParameterEntity] = []
        params_node = self._find_child(func_node, "formal_parameters")
        if not params_node:
            return params

        for child in params_node.children:
            if child.type in ("required_parameter", "optional_parameter"):
                param = self._parse_parameter(child, source)
                if param:
                    params.append(param)

        return params

    def _parse_parameter(self, node: Node, source: bytes) -> ParameterEntity | None:
        """Parse a single parameter node."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return None

        name = self._node_text(name_node, source)

        # Get type annotation
        type_annotation = None
        type_node = self._find_child(node, "type_annotation")
        if type_node and type_node.children:
            type_annotation = self._node_text(type_node.children[-1], source)

        return ParameterEntity(
            name=name,
            type_annotation=type_annotation,
            is_optional=node.type == "optional_parameter",
        )

    def _extract_variable_declarations(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract variable declarations, including arrow functions."""
        for declarator in self._find_children(node, "variable_declarator"):
            name_node = self._find_child(declarator, "identifier")
            if not name_node:
                continue

            name = self._node_text(name_node, source)

            # Check if value is an arrow function
            arrow = self._find_child(declarator, "arrow_function")
            if arrow:
                qualified_name = self._build_qualified_name(name, module=module_name)
                params = self._extract_parameters(arrow, source)

                # Get return type
                return_type = None
                type_annotation = self._find_child(arrow, "type_annotation")
                if type_annotation and type_annotation.children:
                    return_type = self._node_text(type_annotation.children[-1], source)

                is_async = any(c.type == "async" for c in arrow.children)

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
                    language="typescript",
                    parameters=params,
                    return_type=return_type,
                    is_async=is_async,
                    decorators=[],
                )
                result.functions.append(func_entity)

                arrow_body = self._find_child(arrow, "statement_block")
                if arrow_body:
                    self._extract_calls(arrow_body, source, func_entity, result, repo_id, None)
            else:
                # Regular variable
                qualified_name = self._build_qualified_name(name, module=module_name)
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=name,
                        qualified_name=qualified_name,
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=result.file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        language="typescript",
                    )
                )

    # =========================================================================
    # Call-Site Extraction
    # =========================================================================

    def _extract_calls(
        self,
        body_node: Node,
        source: bytes,
        entity: FunctionEntity | MethodEntity,
        result: ExtractionResult,
        repo_id: UUID,
        parent_class: str | None,
    ) -> None:
        """Extract call sites from function/method body."""
        seen: set[str] = set()

        # Regular calls
        for call_node in self._find_descendants(body_node, "call_expression"):
            callee = self._resolve_callee(call_node, source, parent_class)
            if not callee:
                continue
            simple = callee.rsplit(".", 1)[-1]
            if simple in self._SKIP_NAMES or callee in self._SKIP_NAMES or callee in seen:
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

        # new expressions -> INSTANTIATES
        for new_node in self._find_descendants(body_node, "new_expression"):
            callee = self._resolve_new_callee(new_node, source)
            if not callee or callee in seen:
                continue
            seen.add(callee)
            entity.calls.append(callee)
            result.pending_references.append(
                PendingReference(
                    source_entity_id=entity.id,
                    source_qualified_name=entity.qualified_name,
                    source_repository_id=repo_id,
                    target_qualified_name=callee,
                    relation_type=RelationType.INSTANTIATES,
                    line_number=new_node.start_point[0] + 1,
                    context_snippet=self._get_source_line(new_node, source),
                )
            )

    def _resolve_callee(
        self,
        call_node: Node,
        source: bytes,
        parent_class: str | None,
    ) -> str | None:
        """Resolve the callee name from a call_expression node."""
        if not call_node.children:
            return None
        func_child = call_node.children[0]
        if func_child.type == "identifier":
            return self._node_text(func_child, source)
        if func_child.type == "member_expression":
            full_text = self._node_text(func_child, source)
            parts = full_text.split(".")
            if parts[0] == "this" and parent_class:
                class_name = parent_class.rsplit(".", 1)[-1]
                parts[0] = class_name
            return ".".join(parts)
        return None

    def _resolve_new_callee(self, new_node: Node, source: bytes) -> str | None:
        """Resolve the class name from a new_expression node."""
        # new_expression children: "new" keyword + type identifier + arguments
        for child in new_node.children:
            if child.type == "identifier":
                return self._node_text(child, source)
            if child.type == "member_expression":
                return self._node_text(child, source)
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
        - logger.info() -> "logger"
        - ctx.redis.get() -> "ctx.redis"
        - os.path.join() -> "os.path"
        - process_data() -> None (direct call)
        - this.helper() -> None (already resolved to ClassName.method)
        """
        if not call_node.children:
            return None

        func_child = call_node.children[0]

        # Direct identifier call (e.g., func()) has no receiver
        if func_child.type == "identifier":
            return None

        # Member expression (e.g., obj.method() or module.func())
        if func_child.type == "member_expression":
            full_text = self._node_text(func_child, source)
            parts = full_text.split(".")

            # this calls are already resolved to ClassName.method, no receiver needed
            if parts[0] == "this" and parent_class:
                return None

            # Return all parts except the last (method/function name)
            if len(parts) > 1:
                return ".".join(parts[:-1])

        return None
