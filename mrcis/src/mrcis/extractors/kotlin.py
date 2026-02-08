"""Kotlin-specific code extractor using Tree-sitter."""

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


class KotlinExtractor(TreeSitterExtractor):
    """
    Kotlin-specific code extractor.

    Extracts:
    - Package declarations
    - Import statements (including aliased imports)
    - Class/object/interface definitions
    - Data classes and sealed classes
    - Functions (including extension and suspend functions)
    - Properties (val/var)
    - Companion objects
    """

    def get_language_name(self) -> str:
        """Return tree-sitter language name."""
        return "kotlin"

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".kt"}

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Extract entities from Kotlin AST."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="kotlin",
        )

        root = tree.root_node
        package_name = file_path.stem

        # Extract package declaration
        pkg_node = self._find_child(root, "package_header")
        if pkg_node:
            pkg_id = self._find_child(pkg_node, "identifier")
            if pkg_id:
                package_name = self._node_text(pkg_id, source)

        # Extract imports
        self._extract_imports(root, source, result, file_id, repo_id)

        # Extract classes, interfaces, objects
        for node in self._find_descendants(root, "class_declaration"):
            self._extract_class(node, source, result, file_id, repo_id, package_name)

        for node in self._find_descendants(root, "object_declaration"):
            self._extract_object(node, source, result, file_id, repo_id, package_name)

        # Extract top-level functions
        for node in self._find_descendants(root, "function_declaration"):
            # Only process if it's not inside a class body
            if not self._is_inside_class_body(node):
                self._extract_function(node, source, result, file_id, repo_id, package_name)

        # Extract top-level properties
        for node in self._find_descendants(root, "property_declaration"):
            if not self._is_inside_class_body(node):
                self._extract_property(node, source, result, file_id, repo_id, package_name, None)

        return result

    def _is_inside_class_body(self, node: Node) -> bool:
        """Check if a node is inside a class body."""
        parent = node.parent
        while parent:
            if parent.type == "class_body":
                return True
            parent = parent.parent
        return False

    def _extract_imports(
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract import statements."""
        for imp in self._find_descendants(root, "import_header"):
            # Get the import path
            id_node = self._find_child(imp, "identifier")
            if not id_node:
                continue

            module = self._node_text(id_node, source)

            # Check for wildcard import
            wildcard = self._find_child(imp, "wildcard_import")
            if wildcard:
                module += ".*"

            # Check for import alias
            alias = None
            import_alias = self._find_child(imp, "import_alias")
            if import_alias:
                alias_id = self._find_child(import_alias, "type_identifier")
                if not alias_id:
                    alias_id = self._find_child(import_alias, "identifier")
                if alias_id:
                    alias = self._node_text(alias_id, source)

            # Extract imported symbol name
            symbols = []
            if not module.endswith(".*"):
                symbol_name = alias if alias else module.split(".")[-1]
                symbols.append(symbol_name)

            result.imports.append(
                ImportEntity(
                    id=uuid4(),
                    name=symbols[0] if symbols else module.split(".")[-2],
                    qualified_name=module,
                    entity_type=EntityType.IMPORT,
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path=result.file_path,
                    line_start=imp.start_point[0] + 1,
                    line_end=imp.end_point[0] + 1,
                    language="kotlin",
                    source_module=module,
                    imported_symbols=symbols,
                    is_relative=False,
                )
            )

    def _extract_class(  # noqa: PLR0912
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
    ) -> None:
        """Extract a class declaration."""
        # Get class name (simple_identifier inside type_identifier)
        type_id = self._find_child(node, "type_identifier")
        if not type_id:
            return

        name = self._node_text(type_id, source)
        qualified_name = self._build_qualified_name(name, module=package_name)

        # Check for modifiers (abstract, data, sealed, etc.)
        modifiers = self._find_child(node, "modifiers")
        is_abstract = False

        if modifiers:
            for mod in modifiers.children:
                mod_text = self._node_text(mod, source)
                if mod_text == "abstract":
                    is_abstract = True
                elif mod_text in {"data", "sealed"}:
                    pass

        # Check if it's an interface
        is_interface = any(c.type == "interface" for c in node.children)
        if is_interface:
            is_abstract = True

        # Get base classes/interfaces from delegation specifiers
        # Note: delegation_specifier can be direct children of class_declaration
        bases = []
        for specifier in self._find_children(node, "delegation_specifier"):
            # Check for constructor_invocation (class inheritance with constructor call)
            constructor = self._find_child(specifier, "constructor_invocation")
            if constructor:
                user_type = self._find_child(constructor, "user_type")
                if user_type:
                    type_id = self._find_child(user_type, "type_identifier")
                    if type_id:
                        bases.append(self._node_text(type_id, source))
            else:
                # Check for user_type directly (interface implementation)
                user_type = self._find_child(specifier, "user_type")
                if user_type:
                    type_id = self._find_child(user_type, "type_identifier")
                    if type_id:
                        bases.append(self._node_text(type_id, source))

        # Extract annotations
        decorators = self._extract_annotations(node, source)

        # Get docstring (KDoc)
        docstring = self._extract_docstring(node, source)

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
            language="kotlin",
            base_classes=bases,
            decorators=decorators,
            docstring=docstring,
            is_abstract=is_abstract,
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

        # Extract class members
        body = self._find_child(node, "class_body")
        if body:
            self._extract_class_members(
                body, source, result, file_id, repo_id, package_name, qualified_name
            )

    def _extract_object(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
    ) -> None:
        """Extract an object declaration (singleton)."""
        type_id = self._find_child(node, "type_identifier")
        if not type_id:
            # Companion object might not have a name
            # Check if it's a companion object
            if any(
                self._node_text(c, source) == "companion"
                for c in node.children
                if c.type == "modifiers" or c.type in node.children
            ):
                return  # Skip companion objects for now
            return

        name = self._node_text(type_id, source)
        qualified_name = self._build_qualified_name(name, module=package_name)

        # Get delegation specifiers (implemented interfaces)
        bases = []
        for specifier in self._find_children(node, "delegation_specifier"):
            # Check for constructor_invocation
            constructor = self._find_child(specifier, "constructor_invocation")
            if constructor:
                user_type = self._find_child(constructor, "user_type")
                if user_type:
                    type_id = self._find_child(user_type, "type_identifier")
                    if type_id:
                        bases.append(self._node_text(type_id, source))
            else:
                # Check for user_type directly
                user_type = self._find_child(specifier, "user_type")
                if user_type:
                    type_id = self._find_child(user_type, "type_identifier")
                    if type_id:
                        bases.append(self._node_text(type_id, source))

        # Extract annotations
        decorators = self._extract_annotations(node, source)

        # Get docstring
        docstring = self._extract_docstring(node, source)

        # Store object as a class
        object_entity = ClassEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="kotlin",
            base_classes=bases,
            decorators=decorators,
            docstring=docstring,
        )
        result.classes.append(object_entity)

        # Extract object members
        body = self._find_child(node, "class_body")
        if body:
            self._extract_class_members(
                body, source, result, file_id, repo_id, package_name, qualified_name
            )

    def _extract_class_members(
        self,
        body: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
        parent_class: str,
    ) -> None:
        """Extract members from a class body."""
        # Extract functions/methods
        for func in self._find_children(body, "function_declaration"):
            self._extract_method(func, source, result, file_id, repo_id, package_name, parent_class)

        # Extract properties
        for prop in self._find_children(body, "property_declaration"):
            self._extract_property(
                prop, source, result, file_id, repo_id, package_name, parent_class
            )

        # Extract nested classes
        for nested in self._find_children(body, "class_declaration"):
            self._extract_class(nested, source, result, file_id, repo_id, package_name)

        # Extract nested objects
        for nested_obj in self._find_children(body, "object_declaration"):
            self._extract_object(nested_obj, source, result, file_id, repo_id, package_name)

    def _extract_function(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
        parent_class: str | None = None,
    ) -> None:
        """Extract a function declaration."""
        name_node = self._find_child(node, "simple_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, parent=parent_class, module=package_name)

        # Get parameters
        params = self._extract_parameters(node, source)

        # Get return type
        return_type = None
        type_node = self._find_child(node, "type_identifier")
        if not type_node:
            # Try user_type
            user_type = self._find_child(node, "user_type")
            if user_type:
                type_id = self._find_child(user_type, "type_identifier")
                if type_id:
                    return_type = self._node_text(type_id, source)
        else:
            return_type = self._node_text(type_node, source)

        # Check for suspend modifier
        modifiers = self._find_child(node, "modifiers")
        is_suspend = False
        if modifiers:
            is_suspend = any(self._node_text(c, source) == "suspend" for c in modifiers.children)

        # Extract annotations
        decorators = self._extract_annotations(node, source)

        # Get docstring
        docstring = self._extract_docstring(node, source)

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
            language="kotlin",
            parameters=params,
            return_type=return_type,
            is_async=is_suspend,  # suspend functions are async
            decorators=decorators,
            docstring=docstring,
        )
        result.functions.append(func_entity)

        body = self._find_child(node, "function_body")
        if body:
            self._extract_calls(body, source, func_entity, result, repo_id, parent_class)

    def _extract_method(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        _package_name: str,
        parent_class: str,
    ) -> None:
        """Extract a method from a class."""
        name_node = self._find_child(node, "simple_identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, parent=parent_class)

        # Get parameters
        params = self._extract_parameters(node, source)

        # Get return type
        return_type = None
        type_node = self._find_child(node, "type_identifier")
        if not type_node:
            user_type = self._find_child(node, "user_type")
            if user_type:
                type_id = self._find_child(user_type, "type_identifier")
                if type_id:
                    return_type = self._node_text(type_id, source)
        else:
            return_type = self._node_text(type_node, source)

        # Check modifiers
        modifiers = self._find_child(node, "modifiers")
        is_suspend = False
        is_abstract = False

        if modifiers:
            for mod in modifiers.children:
                mod_text = self._node_text(mod, source)
                if mod_text == "suspend":
                    is_suspend = True
                elif mod_text == "override":
                    pass
                elif mod_text == "abstract":
                    is_abstract = True

        # Extract annotations
        decorators = self._extract_annotations(node, source)

        # Get docstring
        docstring = self._extract_docstring(node, source)

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
            language="kotlin",
            parameters=params,
            return_type=return_type,
            is_async=is_suspend,
            is_static=False,  # Kotlin uses companion objects instead of static
            parent_class=parent_class,
            is_constructor=False,
            decorators=decorators,
            docstring=docstring,
            is_abstract=is_abstract,
        )
        result.methods.append(method_entity)

        body = self._find_child(node, "function_body")
        if body:
            self._extract_calls(body, source, method_entity, result, repo_id, parent_class)

    def _extract_property(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
        parent_class: str | None,
    ) -> None:
        """Extract a property declaration."""
        name_node = self._find_child(node, "variable_declaration")
        if name_node:
            id_node = self._find_child(name_node, "simple_identifier")
            if not id_node:
                return
            name = self._node_text(id_node, source)
        else:
            return

        qualified_name = self._build_qualified_name(
            name, parent=parent_class, module=package_name if parent_class is None else None
        )

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
                language="kotlin",
            )
        )

    def _extract_parameters(self, func_node: Node, source: bytes) -> list[ParameterEntity]:
        """Extract function parameters."""
        params: list[ParameterEntity] = []
        params_node = self._find_child(func_node, "function_value_parameters")
        if not params_node:
            return params

        for param in self._find_children(params_node, "parameter"):
            name_node = self._find_child(param, "simple_identifier")
            if not name_node:
                continue

            name = self._node_text(name_node, source)

            # Get type annotation
            type_annotation = None
            type_node = self._find_child(param, "type_identifier")
            if not type_node:
                user_type = self._find_child(param, "user_type")
                if user_type:
                    type_id = self._find_child(user_type, "type_identifier")
                    if type_id:
                        type_annotation = self._node_text(type_id, source)
            else:
                type_annotation = self._node_text(type_node, source)

            # Check if parameter has default value (making it optional)
            has_default = self._find_child(param, "default_value") is not None

            params.append(
                ParameterEntity(
                    name=name,
                    type_annotation=type_annotation,
                    is_optional=has_default,
                )
            )

        return params

    def _extract_annotations(self, node: Node, source: bytes) -> list[str]:
        """Extract annotations from a node."""
        annotations = []

        # Look for annotation modifiers before the node
        modifiers = self._find_child(node, "modifiers")
        if modifiers:
            for child in modifiers.children:
                if child.type == "annotation":
                    annotation_text = self._node_text(child, source)
                    annotations.append(annotation_text)

        return annotations

    def _extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract KDoc comment if present."""
        # Check for comment before the node
        prev = node.prev_sibling
        while prev and prev.type in ("line_comment", "multiline_comment"):
            if prev.type == "multiline_comment":
                comment = self._node_text(prev, source)
                if comment.startswith("/**"):
                    return comment
            prev = prev.prev_sibling
        return None

    # =========================================================================
    # Call-Site Extraction
    # =========================================================================

    _SKIP_NAMES: ClassVar[set[str]] = {
        "println",
        "print",
        "require",
        "check",
        "error",
        "TODO",
        "listOf",
        "mapOf",
        "setOf",
        "arrayOf",
        "mutableListOf",
        "mutableMapOf",
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
        """Extract call sites from a Kotlin function/method body."""
        seen: set[str] = set()

        for call_node in self._find_descendants(body_node, "call_expression"):
            callee = self._resolve_callee(call_node, source, parent_class)
            if not callee:
                continue

            simple = callee.rsplit(".", 1)[-1]
            if simple in self._SKIP_NAMES or callee in seen:
                continue
            seen.add(callee)

            # Uppercase-first heuristic for instantiation (Kotlin has no `new` keyword)
            relation_type = RelationType.INSTANTIATES if simple[0].isupper() else RelationType.CALLS

            # Extract receiver expression (object before the method/function)
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
        """Resolve the callee name from a Kotlin call_expression node."""
        if not call_node.children:
            return None

        first_child = call_node.children[0]

        if first_child.type == "simple_identifier":
            return self._node_text(first_child, source)

        if first_child.type == "navigation_expression":
            full_text = self._node_text(first_child, source)
            parts = full_text.split(".")
            if parts[0] == "this" and parent_class:
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

        Returns the object part before the method name.

        Examples:
        - writer.write() -> "writer"
        - ctx.redis.get() -> "ctx.redis"
        - doWork() -> None (direct call)
        - this.helper() -> None (already resolved to ClassName.method)
        """
        if not call_node.children:
            return None

        first_child = call_node.children[0]

        # Direct identifier call (e.g., func()) has no receiver
        if first_child.type == "simple_identifier":
            return None

        # Navigation expression (e.g., obj.method())
        if first_child.type == "navigation_expression":
            full_text = self._node_text(first_child, source)
            parts = full_text.split(".")

            # this calls are already resolved to ClassName.method, no receiver needed
            if parts[0] == "this" and parent_class:
                return None

            # Return all parts except the last (method name)
            if len(parts) > 1:
                return ".".join(parts[:-1])

        return None
