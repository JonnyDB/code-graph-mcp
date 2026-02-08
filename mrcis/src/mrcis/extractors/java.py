"""Java-specific code extractor using Tree-sitter."""

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


class JavaExtractor(TreeSitterExtractor):
    """
    Java-specific code extractor.

    Extracts:
    - Package declarations
    - Import statements (including static imports)
    - Class/interface/enum definitions
    - Method definitions with annotations
    - Field declarations
    - Constructors
    """

    def get_language_name(self) -> str:
        """Return tree-sitter language name."""
        return "java"

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".java"}

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Extract entities from Java AST."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="java",
        )

        root = tree.root_node
        package_name = file_path.stem

        # Extract package declaration
        pkg_node = self._find_child(root, "package_declaration")
        if pkg_node:
            scoped_id = self._find_child(pkg_node, "scoped_identifier")
            if scoped_id:
                package_name = self._node_text(scoped_id, source)
            else:
                # Single identifier package
                id_node = self._find_child(pkg_node, "identifier")
                if id_node:
                    package_name = self._node_text(id_node, source)

        # Extract imports
        self._extract_imports(root, source, result, file_id, repo_id)

        # Extract classes, interfaces, and enums
        for node in self._find_descendants(root, "class_declaration"):
            self._extract_class(node, source, result, file_id, repo_id, package_name)

        for node in self._find_descendants(root, "interface_declaration"):
            self._extract_interface(node, source, result, file_id, repo_id, package_name)

        for node in self._find_descendants(root, "enum_declaration"):
            self._extract_enum(node, source, result, file_id, repo_id, package_name)

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
        for imp in self._find_descendants(root, "import_declaration"):
            # Get the import path
            scoped_id = self._find_child(imp, "scoped_identifier")
            asterisk_node = self._find_child(imp, "asterisk")

            if scoped_id:
                module = self._node_text(scoped_id, source)
                if asterisk_node:
                    module += ".*"
            else:
                # Single identifier import
                id_node = self._find_child(imp, "identifier")
                if id_node:
                    module = self._node_text(id_node, source)
                    if asterisk_node:
                        module += ".*"
                else:
                    continue

            # Extract imported symbol name
            symbols = []
            if not module.endswith(".*"):
                symbols.append(module.split(".")[-1])

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
                    language="java",
                    source_module=module,
                    imported_symbols=symbols,
                    is_relative=False,
                )
            )

    def _extract_class(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
    ) -> None:
        """Extract a class declaration."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=package_name)

        # Check for abstract modifier
        modifiers = self._find_child(node, "modifiers")
        is_abstract = False
        if modifiers:
            is_abstract = any(
                self._node_text(c, source) == "abstract"
                for c in modifiers.children
                if c.type != "annotation"
            )

        # Get base class from extends
        bases = []
        superclass_node = self._find_child(node, "superclass")
        if superclass_node:
            type_id = self._find_child(superclass_node, "type_identifier")
            if type_id:
                bases.append(self._node_text(type_id, source))

        # Get interfaces from implements
        interfaces_node = self._find_child(node, "super_interfaces")
        if interfaces_node:
            for type_node in self._find_descendants(interfaces_node, "type_identifier"):
                bases.append(self._node_text(type_node, source))

        # Extract annotations
        decorators = self._extract_annotations(modifiers, source) if modifiers else []

        # Get docstring (Javadoc)
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
            language="java",
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

        # Extract methods and fields from class body
        body = self._find_child(node, "class_body")
        if body:
            self._extract_class_members(
                body, source, result, file_id, repo_id, package_name, qualified_name
            )

    def _extract_interface(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
    ) -> None:
        """Extract an interface declaration."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=package_name)

        # Get extended interfaces
        bases = []
        extends_node = self._find_child(node, "extends_interfaces")
        if extends_node:
            for type_node in self._find_descendants(extends_node, "type_identifier"):
                bases.append(self._node_text(type_node, source))

        # Extract annotations
        modifiers = self._find_child(node, "modifiers")
        decorators = self._extract_annotations(modifiers, source) if modifiers else []

        # Get docstring
        docstring = self._extract_docstring(node, source)

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
            language="java",
            base_classes=bases,
            decorators=decorators,
            docstring=docstring,
            is_abstract=True,  # Interfaces are abstract
        )
        result.classes.append(interface_entity)

        # Extract methods from interface body
        body = self._find_child(node, "interface_body")
        if body:
            self._extract_interface_members(
                body, source, result, file_id, repo_id, package_name, qualified_name
            )

    def _extract_enum(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
    ) -> None:
        """Extract an enum declaration."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=package_name)

        # Extract annotations
        modifiers = self._find_child(node, "modifiers")
        decorators = self._extract_annotations(modifiers, source) if modifiers else []

        # Get docstring
        docstring = self._extract_docstring(node, source)

        # Store enum as a class
        enum_entity = ClassEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="java",
            base_classes=[],
            decorators=decorators,
            docstring=docstring,
        )
        result.classes.append(enum_entity)

        # Extract enum body if needed (methods, fields)
        body = self._find_child(node, "enum_body")
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
        """Extract methods and fields from a class body."""
        # Extract methods (including constructors)
        for method in self._find_children(body, "method_declaration"):
            self._extract_method(
                method, source, result, file_id, repo_id, package_name, parent_class
            )

        for constructor in self._find_children(body, "constructor_declaration"):
            self._extract_constructor(
                constructor, source, result, file_id, repo_id, package_name, parent_class
            )

        # Extract fields
        for field in self._find_children(body, "field_declaration"):
            self._extract_field(field, source, result, file_id, repo_id, package_name, parent_class)

    def _extract_interface_members(
        self,
        body: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        package_name: str,
        parent_class: str,
    ) -> None:
        """Extract methods from an interface body."""
        for method in self._find_children(body, "method_declaration"):
            self._extract_method(
                method, source, result, file_id, repo_id, package_name, parent_class
            )

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
        """Extract a method declaration."""
        name_node = self._find_child(node, "identifier")
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
            # Try generic_type, array_type, etc.
            for type_kind in ["generic_type", "array_type", "integral_type", "void_type"]:
                type_node = self._find_child(node, type_kind)
                if type_node:
                    break

        if type_node:
            return_type = self._node_text(type_node, source)

        # Check modifiers
        modifiers = self._find_child(node, "modifiers")
        is_static = False
        is_abstract = False
        if modifiers:
            for mod in modifiers.children:
                if mod.type != "annotation":
                    mod_text = self._node_text(mod, source)
                    if mod_text == "static":
                        is_static = True
                    elif mod_text == "abstract":
                        is_abstract = True

        # Extract annotations
        decorators = self._extract_annotations(modifiers, source) if modifiers else []

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
            language="java",
            parameters=params,
            return_type=return_type,
            is_async=False,  # Java doesn't have async keyword (uses CompletableFuture)
            is_static=is_static,
            parent_class=parent_class,
            is_constructor=False,
            decorators=decorators,
            docstring=docstring,
            is_abstract=is_abstract,
        )
        result.methods.append(method_entity)

        body = self._find_child(node, "block")
        if body:
            self._extract_calls(body, source, method_entity, result, repo_id, parent_class)

    def _extract_constructor(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        _package_name: str,
        parent_class: str,
    ) -> None:
        """Extract a constructor declaration."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, parent=parent_class)

        # Get parameters
        params = self._extract_parameters(node, source)

        # Extract annotations
        modifiers = self._find_child(node, "modifiers")
        decorators = self._extract_annotations(modifiers, source) if modifiers else []

        # Get docstring
        docstring = self._extract_docstring(node, source)

        constructor_entity = MethodEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.METHOD,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="java",
            parameters=params,
            return_type=None,  # Constructors don't have return type
            is_async=False,
            is_static=False,
            parent_class=parent_class,
            is_constructor=True,
            decorators=decorators,
            docstring=docstring,
        )
        result.methods.append(constructor_entity)

        body = self._find_child(node, "constructor_body")
        if body:
            self._extract_calls(body, source, constructor_entity, result, repo_id, parent_class)

    def _extract_field(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        _package_name: str,
        parent_class: str,
    ) -> None:
        """Extract field declarations."""
        # A field_declaration can contain multiple variable_declarators
        for declarator in self._find_children(node, "variable_declarator"):
            name_node = self._find_child(declarator, "identifier")
            if not name_node:
                continue

            name = self._node_text(name_node, source)
            qualified_name = self._build_qualified_name(name, parent=parent_class)

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
                    language="java",
                )
            )

    def _extract_parameters(self, method_node: Node, source: bytes) -> list[ParameterEntity]:
        """Extract method parameters."""
        params: list[ParameterEntity] = []
        params_node = self._find_child(method_node, "formal_parameters")
        if not params_node:
            return params

        for param in self._find_children(params_node, "formal_parameter"):
            name_node = self._find_child(param, "identifier")
            if not name_node:
                continue

            name = self._node_text(name_node, source)

            # Get type annotation
            type_annotation = None
            # Try different type node types
            for type_kind in [
                "type_identifier",
                "generic_type",
                "array_type",
                "integral_type",
            ]:
                type_node = self._find_child(param, type_kind)
                if type_node:
                    type_annotation = self._node_text(type_node, source)
                    break

            params.append(
                ParameterEntity(
                    name=name,
                    type_annotation=type_annotation,
                )
            )

        return params

    def _extract_annotations(self, modifiers_node: Node, source: bytes) -> list[str]:
        """Extract annotations from modifiers node."""
        annotations = []
        for child in modifiers_node.children:
            if child.type in {"annotation", "marker_annotation"}:
                # Get annotation name
                annotation_text = self._node_text(child, source)
                annotations.append(annotation_text)
        return annotations

    def _extract_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract Javadoc comment if present."""
        # Check for block_comment before the node
        prev = node.prev_sibling
        while prev and prev.type in ("line_comment", "block_comment"):
            if prev.type == "block_comment":
                comment = self._node_text(prev, source)
                if comment.startswith("/**"):
                    return comment
            prev = prev.prev_sibling
        return None

    # =========================================================================
    # Call-Site Extraction
    # =========================================================================

    _SKIP_NAMES: ClassVar[set[str]] = set()

    def _extract_calls(
        self,
        body_node: Node,
        source: bytes,
        entity: FunctionEntity | MethodEntity,
        result: ExtractionResult,
        repo_id: UUID,
        parent_class: str | None,
    ) -> None:
        """Extract call sites from a Java method/constructor body."""
        seen: set[str] = set()

        # method_invocation -> CALLS
        for call_node in self._find_descendants(body_node, "method_invocation"):
            callee = self._resolve_method_invocation(call_node, source, parent_class)
            if not callee:
                continue

            simple = callee.rsplit(".", 1)[-1]
            if simple in self._SKIP_NAMES or callee in seen:
                continue
            seen.add(callee)

            # Extract receiver expression (object before the method)
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

        # object_creation_expression -> INSTANTIATES
        for creation_node in self._find_descendants(body_node, "object_creation_expression"):
            callee = self._resolve_object_creation(creation_node, source)
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
                    line_number=creation_node.start_point[0] + 1,
                    context_snippet=self._get_source_line(creation_node, source),
                )
            )

    def _resolve_method_invocation(  # noqa: PLR0911
        self,
        call_node: Node,
        source: bytes,
        parent_class: str | None,
    ) -> str | None:
        """Resolve the callee name from a Java method_invocation node."""
        if not call_node.children:
            return None

        # method_invocation children can be:
        # - identifier (unqualified: doWork())
        # - object.method_name  (qualified: obj.method())
        # The identifier child represents the method name
        # A field_access or identifier before "." is the receiver
        identifiers = self._find_children(call_node, "identifier")
        if not identifiers:
            return None

        # If there's only one identifier, it's an unqualified call
        if len(identifiers) == 1 and call_node.children[0].type == "identifier":
            return self._node_text(identifiers[0], source)

        # For qualified calls, the first child is the receiver, last identifier is the method
        first_child = call_node.children[0]
        method_name = identifiers[-1]
        method_text = self._node_text(method_name, source)

        if first_child.type == "this" and parent_class:
            class_name = parent_class.rsplit(".", 1)[-1]
            return f"{class_name}.{method_text}"

        if first_child.type == "identifier":
            receiver_text = self._node_text(first_child, source)
            return f"{receiver_text}.{method_text}"

        if first_child.type == "field_access":
            receiver_text = self._node_text(first_child, source)
            if receiver_text.startswith("this.") and parent_class:
                class_name = parent_class.rsplit(".", 1)[-1]
                rest = receiver_text[5:]  # strip "this."
                return f"{class_name}.{rest}.{method_text}"
            return f"{receiver_text}.{method_text}"

        # Other cases (e.g., method().method())
        return method_text

    def _resolve_object_creation(
        self,
        creation_node: Node,
        source: bytes,
    ) -> str | None:
        """Resolve the class name from a Java object_creation_expression (new ClassName())."""
        type_id = self._find_child(creation_node, "type_identifier")
        if type_id:
            return self._node_text(type_id, source)
        return None

    def _extract_receiver_expr(  # noqa: PLR0911
        self,
        call_node: Node,
        source: bytes,
        parent_class: str | None,
    ) -> str | None:
        """
        Extract the receiver expression from a method_invocation node.

        Returns the object part before the method name.

        Examples:
        - writer.write() -> "writer"
        - ctx.redis.get() -> "ctx.redis"
        - doWork() -> None (direct call)
        - this.helper() -> None (already resolved to ClassName.method)
        """
        if not call_node.children:
            return None

        # Get identifiers to check if this is qualified
        identifiers = self._find_children(call_node, "identifier")
        if not identifiers:
            return None

        # If there's only one identifier, it's an unqualified call (no receiver)
        if len(identifiers) == 1 and call_node.children[0].type == "identifier":
            return None

        # For qualified calls, extract the receiver
        first_child = call_node.children[0]

        # this calls are already resolved to ClassName.method, no receiver needed
        if first_child.type == "this" and parent_class:
            return None

        if first_child.type == "identifier":
            # Example: obj.method() -> receiver is "obj"
            return self._node_text(first_child, source)

        if first_child.type == "field_access":
            # Handle field_access node (multi-level receiver)
            receiver_text = self._node_text(first_child, source)
            if receiver_text.startswith("this.") and parent_class:
                # Exclude this.field calls (already resolved to ClassName.field.method)
                return None
            # Return the full field access path as receiver
            return receiver_text

        # Other cases (e.g., method().method()) have no stable receiver
        return None
