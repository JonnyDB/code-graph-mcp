"""Ruby-specific code extractor using Tree-sitter.

Supports:
- Standard Ruby: classes, modules, methods, functions, constants, imports
- RSpec DSL: describe, context, it, let, shared_examples, hooks
- Rails DSL: associations, validations, callbacks, scopes, delegates, mixins
- Rake DSL: tasks, namespaces, desc
- Gemfile: gem dependencies
"""

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
    ModuleEntity,
    ParameterEntity,
    VariableEntity,
    Visibility,
)
from mrcis.models.extraction import ExtractionResult
from mrcis.models.relations import PendingReference, RelationType


class RubyExtractor(TreeSitterExtractor):
    """
    Ruby-specific code extractor.

    Extracts:
    - Classes and modules (with visibility, mixins, constants)
    - Methods (instance and class methods) with visibility tracking
    - Imports (require/require_relative)
    - attr_* declarations
    - Functions (top-level methods)
    - RSpec DSL (describe, it, let, shared_examples, hooks)
    - Rails DSL (associations, validations, callbacks, scopes, delegates)
    - Rake DSL (tasks, namespaces)
    - Gemfile dependencies
    """

    # =========================================================================
    # RSpec DSL Constants
    # =========================================================================

    _RSPEC_DESCRIBE_METHODS: ClassVar[set[str]] = {
        "describe",
        "context",
        "feature",
    }
    _RSPEC_EXAMPLE_METHODS: ClassVar[set[str]] = {
        "it",
        "specify",
        "example",
    }
    _RSPEC_LET_METHODS: ClassVar[set[str]] = {
        "let",
        "let!",
        "subject",
    }
    _RSPEC_SHARED_METHODS: ClassVar[set[str]] = {
        "shared_examples",
        "shared_examples_for",
        "shared_context",
    }
    _RSPEC_HOOK_METHODS: ClassVar[set[str]] = {
        "before",
        "after",
        "around",
    }
    _RSPEC_INCLUDE_METHODS: ClassVar[set[str]] = {
        "it_behaves_like",
        "include_examples",
        "include_context",
        "it_should_behave_like",
    }

    # =========================================================================
    # Rails DSL Constants
    # =========================================================================

    _RAILS_ASSOCIATION_METHODS: ClassVar[set[str]] = {
        "has_many",
        "has_one",
        "belongs_to",
        "has_and_belongs_to_many",
    }
    _RAILS_VALIDATION_METHODS: ClassVar[set[str]] = {
        "validates",
        "validate",
        "validates_presence_of",
        "validates_uniqueness_of",
        "validates_format_of",
        "validates_length_of",
        "validates_numericality_of",
        "validates_inclusion_of",
        "validates_exclusion_of",
        "validates_acceptance_of",
        "validates_confirmation_of",
        "validates_associated",
    }
    _RAILS_CALLBACK_METHODS: ClassVar[set[str]] = {
        "before_action",
        "after_action",
        "around_action",
        "before_save",
        "after_save",
        "around_save",
        "before_create",
        "after_create",
        "around_create",
        "before_update",
        "after_update",
        "around_update",
        "before_destroy",
        "after_destroy",
        "around_destroy",
        "before_validation",
        "after_validation",
        "after_commit",
        "after_rollback",
        "after_initialize",
        "after_find",
        "before_filter",
        "after_filter",
        "around_filter",
        "skip_before_action",
        "skip_after_action",
    }

    # =========================================================================
    # Call-Site Skip List
    # =========================================================================

    _SKIP_NAMES: ClassVar[set[str]] = {
        "puts",
        "print",
        "p",
        "pp",
        "raise",
        "require",
        "require_relative",
        "attr_reader",
        "attr_writer",
        "attr_accessor",
    }

    # =========================================================================
    # Mixin Methods
    # =========================================================================

    _MIXIN_METHODS: ClassVar[set[str]] = {"include", "extend", "prepend"}

    # =========================================================================
    # Visibility Mapping
    # =========================================================================

    _VISIBILITY_MAP: ClassVar[dict[str, Visibility]] = {
        "private": Visibility.PRIVATE,
        "protected": Visibility.PROTECTED,
        "public": Visibility.PUBLIC,
    }

    def get_language_name(self) -> str:
        """Return tree-sitter language name."""
        return "ruby"

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".rb", ".rake", ".gemspec"}

    def supports(self, file_path: Path) -> bool:
        """Check if file is a Ruby file."""
        if file_path.suffix.lower() in self.get_supported_extensions():
            return True
        return file_path.name in ("Rakefile", "Gemfile", "Guardfile", "Capfile", "Vagrantfile")

    def _extract_from_tree(
        self,
        tree: Tree,
        source: bytes,
        file_path: Path,
        file_id: UUID,
        repo_id: UUID,
    ) -> ExtractionResult:
        """Extract entities from Ruby AST."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="ruby",
        )

        root = tree.root_node
        module_name = file_path.stem
        file_name = file_path.name

        is_rakefile = file_name == "Rakefile" or file_path.suffix == ".rake"
        is_gemfile = file_name == "Gemfile"
        is_spec = "_spec" in file_path.stem or "/spec/" in str(file_path)

        # Always extract requires
        self._extract_requires(root, source, result, file_id, repo_id)

        # Gemfile: extract gem deps and return
        if is_gemfile:
            self._extract_gemfile_deps(root, source, result, file_id, repo_id)
            return result

        # Standard structural extraction (always)
        for node in self._find_descendants(root, "class"):
            self._extract_class(node, source, result, file_id, repo_id, module_name)

        for node in self._find_descendants(root, "module"):
            self._extract_module(node, source, result, file_id, repo_id, module_name)

        # Extract top-level methods (functions)
        for node in self._find_descendants(root, "method"):
            if not self._is_inside_class_or_module_or_block(node):
                self._extract_function(node, source, result, file_id, repo_id, module_name)

        # Extract top-level constants
        self._extract_constants(root, source, result, file_id, repo_id, parent_name=None)

        # DSL extraction
        if is_spec:
            self._extract_rspec_dsl(root, source, result, file_id, repo_id, module_name)
        if is_rakefile:
            self._extract_rake_dsl(root, source, result, file_id, repo_id, module_name)

        return result

    # =========================================================================
    # Guard Helpers
    # =========================================================================

    def _is_inside_class_or_module_or_block(self, node: Node) -> bool:
        """Check if a node is inside a class, module, or DSL block."""
        parent = node.parent
        while parent:
            if parent.type in ("class", "module"):
                return True
            if (
                parent.type in ("do_block", "block")
                and parent.parent
                and parent.parent.type == "call"
            ):
                return True
            parent = parent.parent
        return False

    # =========================================================================
    # Ruby Comment Docstring Extraction
    # =========================================================================

    def _get_ruby_docstring(self, node: Node, source: bytes) -> str | None:
        """Extract Ruby comment block above a definition as docstring."""
        if node.parent is None:
            return None

        comments = self._collect_comments_above(node, source)

        # tree-sitter-ruby places the first comment before body_statement at the
        # class/module level. If we found nothing and this node is the first
        # meaningful child of a body_statement, look at the grandparent's children
        # for comments just before the body_statement.
        if not comments and node.parent.type == "body_statement":
            body = node.parent
            first_meaningful = next(
                (c for c in body.children if c.type not in ("comment",)),
                None,
            )
            if first_meaningful is not None and first_meaningful.id == node.id:
                comments = self._collect_comments_above(body, source)

        return "\n".join(comments) if comments else None

    def _collect_comments_above(self, node: Node, source: bytes) -> list[str]:
        """Collect consecutive comment lines immediately before a node."""
        if node.parent is None:
            return []

        siblings = node.parent.children
        node_index = None
        for i, sibling in enumerate(siblings):
            if sibling.id == node.id:
                node_index = i
                break

        if node_index is None:
            return []

        comments: list[str] = []
        for i in range(node_index - 1, -1, -1):
            sibling = siblings[i]
            if sibling.type == "comment":
                text = self._node_text(sibling, source)
                text = text.lstrip("#")
                if text.startswith(" "):
                    text = text[1:]
                comments.insert(0, text.strip())
            else:
                break

        return comments

    # =========================================================================
    # Visibility Tracking
    # =========================================================================

    def _compute_visibility_map(self, body_node: Node, source: bytes) -> dict[str, Visibility]:
        """Build a map of method_name -> visibility from visibility modifiers."""
        visibility_map: dict[str, Visibility] = {}
        current_visibility = Visibility.PUBLIC

        for child in body_node.children:
            if child.type == "call":
                method_node = self._find_child(child, "identifier")
                if not method_node:
                    continue
                method_name = self._node_text(method_node, source)

                if method_name in self._VISIBILITY_MAP:
                    vis = self._VISIBILITY_MAP[method_name]
                    arg_list = self._find_child(child, "argument_list")
                    if arg_list:
                        # Inline: private :method_name, :other_method
                        for sym in self._find_children(arg_list, "simple_symbol"):
                            sym_name = self._node_text(sym, source).lstrip(":")
                            visibility_map[sym_name] = vis
                    else:
                        # Block-style: changes default for subsequent methods
                        current_visibility = vis
            elif child.type == "identifier":
                text = self._node_text(child, source)
                if text in self._VISIBILITY_MAP:
                    current_visibility = self._VISIBILITY_MAP[text]
            elif child.type == "method":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    mname = self._node_text(name_node, source)
                    if mname not in visibility_map:
                        visibility_map[mname] = current_visibility

        return visibility_map

    # =========================================================================
    # Import Extraction
    # =========================================================================

    def _extract_requires(
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract require and require_relative statements."""
        for call in self._find_descendants(root, "call"):
            method_node = self._find_child(call, "identifier")
            if not method_node:
                continue

            method_name = self._node_text(method_node, source)
            if method_name not in ("require", "require_relative"):
                continue

            arg_list = self._find_child(call, "argument_list")
            if not arg_list:
                continue

            string_node = self._find_child(arg_list, "string")
            if not string_node:
                continue

            content_node = self._find_child(string_node, "string_content")
            if not content_node:
                continue

            module = self._node_text(content_node, source)
            is_relative = method_name == "require_relative"

            result.imports.append(
                ImportEntity(
                    id=uuid4(),
                    name=module.split("/")[-1],
                    qualified_name=module,
                    entity_type=EntityType.IMPORT,
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path=result.file_path,
                    line_start=call.start_point[0] + 1,
                    line_end=call.end_point[0] + 1,
                    language="ruby",
                    source_module=module,
                    imported_symbols=[module],
                    is_relative=is_relative,
                )
            )

    # =========================================================================
    # Class Extraction
    # =========================================================================

    def _extract_class(  # noqa: PLR0912
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a class declaration."""
        name = ""
        name_node = self._find_child(node, "constant")
        if name_node:
            name = self._node_text(name_node, source)
        else:
            scope_node = self._find_child(node, "scope_resolution")
            if scope_node:
                name = self._node_text(scope_node, source)

        if not name:
            return

        qualified_name = self._build_qualified_name(name, module=module_name)

        # Get base class (superclass)
        bases: list[str] = []
        superclass_node = self._find_child(node, "superclass")
        if superclass_node:
            const_node = self._find_child(superclass_node, "constant")
            if const_node:
                bases.append(self._node_text(const_node, source))
            else:
                scope_node = self._find_child(superclass_node, "scope_resolution")
                if scope_node:
                    bases.append(self._node_text(scope_node, source))

        docstring = self._get_ruby_docstring(node, source)

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
            language="ruby",
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

        body = self._find_child(node, "body_statement")
        if body:
            # Compute visibility map once for all methods
            visibility_map = self._compute_visibility_map(body, source)

            # Extract instance methods
            for method in self._find_children(body, "method"):
                method_name_node = self._find_child(method, "identifier")
                vis = Visibility.PUBLIC
                if method_name_node:
                    mname = self._node_text(method_name_node, source)
                    vis = visibility_map.get(mname, Visibility.PUBLIC)
                self._extract_method(
                    method,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    name,
                    visibility=vis,
                )
                # Track method names on class entity
                if method_name_node:
                    class_entity.method_names.append(self._node_text(method_name_node, source))

            # Extract class methods (singleton methods)
            for method in self._find_children(body, "singleton_method"):
                self._extract_method(
                    method,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    name,
                    is_static=True,
                )
                sm_name_node = self._find_child(method, "identifier")
                if sm_name_node:
                    class_entity.method_names.append(self._node_text(sm_name_node, source))

            # Extract attr_* declarations
            self._extract_attrs(node, source, result, file_id, repo_id, name)

            # Extract constants
            self._extract_constants(body, source, result, file_id, repo_id, parent_name=name)

            # Extract mixins (include/extend/prepend)
            self._extract_mixins(body, source, result, repo_id, class_entity)

            # Extract Rails DSL (associations, validations, callbacks, scopes, delegates)
            self._extract_rails_dsl(body, source, result, file_id, repo_id, class_entity)

    # =========================================================================
    # Module Extraction
    # =========================================================================

    def _extract_module(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a module declaration."""
        name = ""
        name_node = self._find_child(node, "constant")
        if name_node:
            name = self._node_text(name_node, source)
        else:
            scope_node = self._find_child(node, "scope_resolution")
            if scope_node:
                name = self._node_text(scope_node, source)

        if not name:
            return

        qualified_name = self._build_qualified_name(name, module=module_name)
        docstring = self._get_ruby_docstring(node, source)

        module_entity = ModuleEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.MODULE,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="ruby",
            docstring=docstring,
            exports=[],
        )
        result.modules.append(module_entity)

        body = self._find_child(node, "body_statement")
        if body:
            visibility_map = self._compute_visibility_map(body, source)

            for method in self._find_children(body, "method"):
                method_name_node = self._find_child(method, "identifier")
                vis = Visibility.PUBLIC
                if method_name_node:
                    mname = self._node_text(method_name_node, source)
                    vis = visibility_map.get(mname, Visibility.PUBLIC)
                    module_entity.exports.append(mname)
                self._extract_method(
                    method,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    name,
                    visibility=vis,
                )

            for method in self._find_children(body, "singleton_method"):
                self._extract_method(
                    method,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    name,
                    is_static=True,
                )
                sm_name_node = self._find_child(method, "identifier")
                if sm_name_node:
                    module_entity.exports.append(self._node_text(sm_name_node, source))

            # Extract constants
            self._extract_constants(body, source, result, file_id, repo_id, parent_name=name)

            # Extract mixins
            self._extract_mixins(body, source, result, repo_id, module_entity)

    # =========================================================================
    # Method Extraction
    # =========================================================================

    def _extract_method(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        parent_class: str,
        is_static: bool = False,
        visibility: Visibility = Visibility.PUBLIC,
    ) -> None:
        """Extract a method from a class or module."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, parent=parent_class, module=module_name)
        params = self._extract_parameters(node, source)
        docstring = self._get_ruby_docstring(node, source)

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
            language="ruby",
            parameters=params,
            return_type=None,
            is_async=False,
            is_static=is_static,
            parent_class=parent_class,
            is_constructor=name == "initialize",
            visibility=visibility,
            docstring=docstring,
        )
        result.methods.append(method_entity)

        body = self._find_child(node, "body_statement")
        if body:
            self._extract_calls(body, source, method_entity, result, repo_id, parent_class)

    # =========================================================================
    # Function Extraction (top-level)
    # =========================================================================

    def _extract_function(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract a top-level function (method outside class/module)."""
        name_node = self._find_child(node, "identifier")
        if not name_node:
            return

        name = self._node_text(name_node, source)
        qualified_name = self._build_qualified_name(name, module=module_name)
        params = self._extract_parameters(node, source)
        docstring = self._get_ruby_docstring(node, source)

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
            language="ruby",
            parameters=params,
            return_type=None,
            is_async=False,
            decorators=[],
            docstring=docstring,
        )
        result.functions.append(func_entity)

        body = self._find_child(node, "body_statement")
        if body:
            self._extract_calls(body, source, func_entity, result, repo_id, parent_class=None)

    # =========================================================================
    # Parameter Extraction
    # =========================================================================

    def _extract_parameters(self, method_node: Node, source: bytes) -> list[ParameterEntity]:
        """Extract method parameters."""
        params: list[ParameterEntity] = []
        params_node = self._find_child(method_node, "method_parameters")
        if not params_node:
            return params

        for child in params_node.children:
            if child.type == "identifier":
                params.append(
                    ParameterEntity(
                        name=self._node_text(child, source),
                        type_annotation=None,
                    )
                )
            elif child.type == "optional_parameter":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    params.append(
                        ParameterEntity(
                            name=self._node_text(name_node, source),
                            type_annotation=None,
                            is_optional=True,
                        )
                    )
            elif child.type == "splat_parameter":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    params.append(
                        ParameterEntity(
                            name=f"*{self._node_text(name_node, source)}",
                            type_annotation=None,
                        )
                    )
            elif child.type == "hash_splat_parameter":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    params.append(
                        ParameterEntity(
                            name=f"**{self._node_text(name_node, source)}",
                            type_annotation=None,
                        )
                    )
            elif child.type == "block_parameter":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    params.append(
                        ParameterEntity(
                            name=f"&{self._node_text(name_node, source)}",
                            type_annotation=None,
                        )
                    )

        return params

    # =========================================================================
    # Attribute Extraction (attr_reader/attr_writer/attr_accessor)
    # =========================================================================

    def _extract_attrs(
        self,
        class_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        parent_class: str,
    ) -> None:
        """Extract attr_reader, attr_writer, attr_accessor declarations."""
        body = self._find_child(class_node, "body_statement")
        if not body:
            return

        for child in body.children:
            if child.type != "call":
                continue

            method_node = self._find_child(child, "identifier")
            if not method_node:
                continue

            method_name = self._node_text(method_node, source)
            if method_name not in ("attr_reader", "attr_writer", "attr_accessor"):
                continue

            arg_list = self._find_child(child, "argument_list")
            if not arg_list:
                continue

            for symbol in self._find_children(arg_list, "simple_symbol"):
                symbol_text = self._node_text(symbol, source).lstrip(":")
                qualified_name = self._build_qualified_name(symbol_text, parent=parent_class)

                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=symbol_text,
                        qualified_name=qualified_name,
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=result.file_path,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        language="ruby",
                        parent_class=parent_class,
                    )
                )

    # =========================================================================
    # Constant Extraction
    # =========================================================================

    def _extract_constants(
        self,
        body_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        parent_name: str | None,
    ) -> None:
        """Extract constant assignments (UPPER_CASE = value)."""
        for assignment in self._find_children(body_node, "assignment"):
            if not assignment.children:
                continue
            left = assignment.children[0]
            if left.type == "constant":
                name = self._node_text(left, source)
                qualified_name = self._build_qualified_name(name, parent=parent_name)

                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=name,
                        qualified_name=qualified_name,
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=result.file_path,
                        line_start=assignment.start_point[0] + 1,
                        line_end=assignment.end_point[0] + 1,
                        language="ruby",
                        is_constant=True,
                        parent_class=parent_name,
                    )
                )

    # =========================================================================
    # Mixin Extraction (include/extend/prepend)
    # =========================================================================

    def _extract_mixins(
        self,
        body_node: Node,
        source: bytes,
        result: ExtractionResult,
        repo_id: UUID,
        parent_entity: ClassEntity | ModuleEntity,
    ) -> None:
        """Extract include/extend/prepend as mixin references."""
        for child in body_node.children:
            if child.type != "call":
                continue

            method_node = self._find_child(child, "identifier")
            if not method_node:
                continue

            method_name = self._node_text(method_node, source)
            if method_name not in self._MIXIN_METHODS:
                continue

            arg_list = self._find_child(child, "argument_list")
            if not arg_list:
                continue

            for arg in arg_list.children:
                if arg.type in ("constant", "scope_resolution"):
                    mixin_name = self._node_text(arg, source)

                    if isinstance(parent_entity, ClassEntity):
                        parent_entity.mixins.append(mixin_name)

                    result.pending_references.append(
                        PendingReference(
                            source_entity_id=parent_entity.id,
                            source_qualified_name=parent_entity.qualified_name,
                            source_repository_id=repo_id,
                            target_qualified_name=mixin_name,
                            relation_type=RelationType.IMPLEMENTS,
                            line_number=child.start_point[0] + 1,
                            context_snippet=self._get_source_line(child, source),
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
        """Extract call sites from a Ruby function/method body."""
        seen: set[str] = set()

        for call_node in self._find_descendants(body_node, "call"):
            callee = self._resolve_callee(call_node, source, parent_class)
            if not callee:
                continue

            simple = callee.rsplit(".", 1)[-1]
            if simple in self._SKIP_NAMES or callee in seen:
                continue
            seen.add(callee)

            relation_type = RelationType.INSTANTIATES if simple == "new" else RelationType.CALLS

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
                )
            )

    def _resolve_callee(
        self,
        call_node: Node,
        source: bytes,
        parent_class: str | None,
    ) -> str | None:
        """Resolve the callee name from a Ruby call node."""
        if not call_node.children:
            return None

        method_node = self._find_child(call_node, "identifier")
        if not method_node:
            return None

        method_name = self._node_text(method_node, source)

        receiver = None
        first_child = call_node.children[0]
        if first_child != method_node:
            receiver_text = self._node_text(first_child, source)
            if receiver_text == "self" and parent_class:
                class_name = parent_class.rsplit(".", 1)[-1]
                receiver = class_name
            else:
                receiver = receiver_text

        if receiver:
            return f"{receiver}.{method_name}"
        return method_name

    # =========================================================================
    # RSpec DSL Extraction
    # =========================================================================

    def _get_call_method_name(self, call_node: Node, source: bytes) -> str | None:
        """Get the simple method name from a call node."""
        method_node = self._find_child(call_node, "identifier")
        if method_node:
            return self._node_text(method_node, source)
        return None

    def _get_call_description(self, call_node: Node, source: bytes) -> str | None:
        """Get the description string, constant, or symbol from a call's argument list."""
        arg_list = self._find_child(call_node, "argument_list")
        if not arg_list:
            return None

        for arg in arg_list.children:
            if arg.type == "string":
                content = self._find_child(arg, "string_content")
                if content:
                    return self._node_text(content, source)
            elif arg.type in ("constant", "scope_resolution"):
                return self._node_text(arg, source)
            elif arg.type == "simple_symbol":
                return self._node_text(arg, source).lstrip(":")
        return None

    def _get_call_block(self, call_node: Node) -> Node | None:
        """Get the do_block or block (curly brace) from a call node."""
        block = self._find_child(call_node, "do_block")
        if block:
            return block
        return self._find_child(call_node, "block")

    def _extract_rspec_dsl(
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract RSpec DSL constructs (describe, it, let, etc.)."""
        self._walk_rspec_node(
            root,
            source,
            result,
            file_id,
            repo_id,
            module_name,
            context_stack=[],
        )

    def _walk_rspec_node(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        context_stack: list[tuple[str, UUID]],
    ) -> None:
        """Recursively walk AST looking for RSpec DSL patterns."""
        for child in node.children:
            if child.type not in ("call", "do_block", "block", "body_statement", "program"):
                continue

            if child.type != "call":
                self._walk_rspec_node(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                )
                continue

            method_name = self._get_call_method_name(child, source)
            if not method_name:
                self._walk_rspec_node(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                )
                continue

            if method_name in self._RSPEC_DESCRIBE_METHODS or (
                method_name == "describe" and self._is_rspec_describe(child, source)
            ):
                self._handle_rspec_describe(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                    method_name,
                )
            elif method_name in self._RSPEC_EXAMPLE_METHODS:
                self._handle_rspec_example(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                )
            elif method_name in self._RSPEC_LET_METHODS:
                self._handle_rspec_let(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                    method_name,
                )
            elif method_name in self._RSPEC_SHARED_METHODS:
                self._handle_rspec_shared(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                )
            elif method_name in self._RSPEC_HOOK_METHODS:
                self._handle_rspec_hook(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                    method_name,
                )
            elif method_name in self._RSPEC_INCLUDE_METHODS:
                self._handle_rspec_include(
                    child,
                    source,
                    result,
                    repo_id,
                    module_name,
                    context_stack,
                )
            else:
                # Recurse into non-RSpec calls (they might contain blocks with RSpec calls)
                self._walk_rspec_node(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    context_stack,
                )

    def _is_rspec_describe(self, call_node: Node, source: bytes) -> bool:
        """Check if a describe call is an RSpec.describe (has RSpec receiver)."""
        if not call_node.children:
            return False
        first_child = call_node.children[0]
        if first_child.type == "scope_resolution":
            return self._node_text(first_child, source).startswith("RSpec")
        return True

    def _handle_rspec_describe(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        context_stack: list[tuple[str, UUID]],
        method_name: str,
    ) -> None:
        """Handle RSpec.describe / describe / context blocks."""
        description = self._get_call_description(call_node, source) or "anonymous"
        name = description

        parent = ".".join(cs[0] for cs in context_stack) if context_stack else None
        qualified_name = self._build_qualified_name(name, parent=parent, module=module_name)

        class_entity = ClassEntity(
            id=uuid4(),
            name=name,
            qualified_name=qualified_name,
            entity_type=EntityType.CLASS,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=call_node.start_point[0] + 1,
            line_end=call_node.end_point[0] + 1,
            language="ruby",
            base_classes=[],
            decorators=[method_name],
        )
        result.classes.append(class_entity)

        # If describing a constant (class under test), create pending reference
        arg_list = self._find_child(call_node, "argument_list")
        if arg_list:
            for arg in arg_list.children:
                if arg.type in ("constant", "scope_resolution"):
                    target = self._node_text(arg, source)
                    result.pending_references.append(
                        PendingReference(
                            source_entity_id=class_entity.id,
                            source_qualified_name=qualified_name,
                            source_repository_id=repo_id,
                            target_qualified_name=target,
                            relation_type=RelationType.REFERENCES,
                            line_number=call_node.start_point[0] + 1,
                            context_snippet=self._get_source_line(call_node, source),
                        )
                    )
                    break

        # Recurse into the block
        block = self._get_call_block(call_node)
        if block:
            self._walk_rspec_node(
                block,
                source,
                result,
                file_id,
                repo_id,
                module_name,
                [*context_stack, (name, class_entity.id)],
            )

    def _handle_rspec_example(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        context_stack: list[tuple[str, UUID]],
    ) -> None:
        """Handle RSpec it/specify/example blocks as MethodEntity."""
        description = self._get_call_description(call_node, source) or "anonymous example"

        parent = ".".join(cs[0] for cs in context_stack) if context_stack else module_name
        qualified_name = self._build_qualified_name(description, parent=parent)

        method_entity = MethodEntity(
            id=uuid4(),
            name=description,
            qualified_name=qualified_name,
            entity_type=EntityType.METHOD,
            repository_id=repo_id,
            file_id=file_id,
            file_path=result.file_path,
            line_start=call_node.start_point[0] + 1,
            line_end=call_node.end_point[0] + 1,
            language="ruby",
            parameters=[],
            return_type=None,
            is_async=False,
            is_static=False,
            parent_class=parent,
            decorators=["example"],
        )
        result.methods.append(method_entity)

        block = self._get_call_block(call_node)
        if block:
            self._extract_calls(
                block,
                source,
                method_entity,
                result,
                repo_id,
                parent_class=parent,
            )

    def _handle_rspec_let(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        context_stack: list[tuple[str, UUID]],
        method_name: str,
    ) -> None:
        """Handle RSpec let/let!/subject as VariableEntity."""
        var_name = self._get_call_description(call_node, source) or method_name

        parent = ".".join(cs[0] for cs in context_stack) if context_stack else None
        qualified_name = self._build_qualified_name(
            var_name,
            parent=parent,
            module=module_name,
        )

        result.variables.append(
            VariableEntity(
                id=uuid4(),
                name=var_name,
                qualified_name=qualified_name,
                entity_type=EntityType.VARIABLE,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=call_node.start_point[0] + 1,
                line_end=call_node.end_point[0] + 1,
                language="ruby",
                decorators=[method_name],
            )
        )

    def _handle_rspec_shared(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        context_stack: list[tuple[str, UUID]],
    ) -> None:
        """Handle shared_examples/shared_context as FunctionEntity."""
        name = self._get_call_description(call_node, source) or "anonymous shared"
        qualified_name = self._build_qualified_name(name, module=module_name)

        result.functions.append(
            FunctionEntity(
                id=uuid4(),
                name=name,
                qualified_name=qualified_name,
                entity_type=EntityType.FUNCTION,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=call_node.start_point[0] + 1,
                line_end=call_node.end_point[0] + 1,
                language="ruby",
                parameters=[],
                return_type=None,
                is_async=False,
                decorators=["shared_examples"],
            )
        )

        block = self._get_call_block(call_node)
        if block:
            self._walk_rspec_node(
                block,
                source,
                result,
                file_id,
                repo_id,
                module_name,
                [*context_stack, (name, uuid4())],
            )

    def _handle_rspec_hook(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        context_stack: list[tuple[str, UUID]],
        method_name: str,
    ) -> None:
        """Handle before/after/around hooks as MethodEntity."""
        hook_type = self._get_call_description(call_node, source) or "each"
        name = f"{method_name}_{hook_type}"

        parent = ".".join(cs[0] for cs in context_stack) if context_stack else module_name
        qualified_name = self._build_qualified_name(name, parent=parent)

        result.methods.append(
            MethodEntity(
                id=uuid4(),
                name=name,
                qualified_name=qualified_name,
                entity_type=EntityType.METHOD,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=call_node.start_point[0] + 1,
                line_end=call_node.end_point[0] + 1,
                language="ruby",
                parameters=[],
                return_type=None,
                is_async=False,
                is_static=False,
                parent_class=parent,
                decorators=[method_name],
            )
        )

    def _handle_rspec_include(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        repo_id: UUID,
        module_name: str,
        context_stack: list[tuple[str, UUID]],
    ) -> None:
        """Handle it_behaves_like/include_examples as PendingReference."""
        target_name = self._get_call_description(call_node, source)
        if not target_name:
            return

        if context_stack:
            source_name = ".".join(cs[0] for cs in context_stack)
            source_id = context_stack[-1][1]
        else:
            source_name = module_name
            source_id = uuid4()

        result.pending_references.append(
            PendingReference(
                source_entity_id=source_id,
                source_qualified_name=source_name,
                source_repository_id=repo_id,
                target_qualified_name=target_name,
                relation_type=RelationType.REFERENCES,
                line_number=call_node.start_point[0] + 1,
                context_snippet=self._get_source_line(call_node, source),
            )
        )

    # =========================================================================
    # Rails DSL Extraction
    # =========================================================================

    def _extract_rails_dsl(
        self,
        body_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        class_entity: ClassEntity,
    ) -> None:
        """Extract Rails DSL constructs from a class body."""
        for child in body_node.children:
            if child.type != "call":
                continue

            method_node = self._find_child(child, "identifier")
            if not method_node:
                continue

            method_name = self._node_text(method_node, source)

            if method_name in self._RAILS_ASSOCIATION_METHODS:
                self._handle_rails_association(
                    child,
                    source,
                    result,
                    repo_id,
                    class_entity,
                    method_name,
                )
            elif method_name in self._RAILS_VALIDATION_METHODS:
                self._handle_rails_validation(child, source, class_entity)
            elif method_name in self._RAILS_CALLBACK_METHODS:
                self._handle_rails_callback(child, source, class_entity, method_name)
            elif method_name == "scope":
                self._handle_rails_scope(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    class_entity,
                )
            elif method_name == "delegate":
                self._handle_rails_delegate(
                    child,
                    source,
                    result,
                    repo_id,
                    class_entity,
                )

    def _handle_rails_association(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        repo_id: UUID,
        class_entity: ClassEntity,
        method_name: str,
    ) -> None:
        """Handle has_many/has_one/belongs_to as PendingReference."""
        arg_list = self._find_child(call_node, "argument_list")
        if not arg_list:
            return

        for arg in arg_list.children:
            if arg.type == "simple_symbol":
                assoc_name = self._node_text(arg, source).lstrip(":")

                # Infer target class name from association name
                if method_name in ("has_many", "has_and_belongs_to_many"):
                    target = assoc_name.rstrip("s").capitalize()
                else:
                    target = assoc_name.capitalize()

                result.pending_references.append(
                    PendingReference(
                        source_entity_id=class_entity.id,
                        source_qualified_name=class_entity.qualified_name,
                        source_repository_id=repo_id,
                        target_qualified_name=target,
                        relation_type=RelationType.REFERENCES,
                        line_number=call_node.start_point[0] + 1,
                        context_snippet=self._get_source_line(call_node, source),
                    )
                )
                break

    def _handle_rails_validation(
        self,
        call_node: Node,
        source: bytes,
        class_entity: ClassEntity,
    ) -> None:
        """Store validates/validate as decorator on ClassEntity."""
        snippet = self._get_source_line(call_node, source)
        class_entity.decorators.append(snippet)

    def _handle_rails_callback(
        self,
        call_node: Node,
        source: bytes,
        class_entity: ClassEntity,
        method_name: str,
    ) -> None:
        """Store callbacks (before_action etc.) as decorators on ClassEntity."""
        snippet = self._get_source_line(call_node, source)
        class_entity.decorators.append(f"{method_name}: {snippet}")

    def _handle_rails_scope(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        class_entity: ClassEntity,
    ) -> None:
        """Handle scope :name, -> { ... } as MethodEntity."""
        arg_list = self._find_child(call_node, "argument_list")
        if not arg_list:
            return

        for arg in arg_list.children:
            if arg.type == "simple_symbol":
                scope_name = self._node_text(arg, source).lstrip(":")
                qualified_name = self._build_qualified_name(
                    scope_name,
                    parent=class_entity.name,
                )

                result.methods.append(
                    MethodEntity(
                        id=uuid4(),
                        name=scope_name,
                        qualified_name=qualified_name,
                        entity_type=EntityType.METHOD,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=result.file_path,
                        line_start=call_node.start_point[0] + 1,
                        line_end=call_node.end_point[0] + 1,
                        language="ruby",
                        parameters=[],
                        return_type=None,
                        is_async=False,
                        is_static=True,
                        parent_class=class_entity.name,
                        decorators=["scope"],
                    )
                )
                class_entity.method_names.append(scope_name)
                break

    def _handle_rails_delegate(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        repo_id: UUID,
        class_entity: ClassEntity,
    ) -> None:
        """Handle delegate :method, to: :target as PendingReference."""
        arg_list = self._find_child(call_node, "argument_list")
        if not arg_list:
            return

        for arg in arg_list.children:
            if arg.type == "simple_symbol":
                method_name = self._node_text(arg, source).lstrip(":")
                result.pending_references.append(
                    PendingReference(
                        source_entity_id=class_entity.id,
                        source_qualified_name=class_entity.qualified_name,
                        source_repository_id=repo_id,
                        target_qualified_name=method_name,
                        relation_type=RelationType.CALLS,
                        line_number=call_node.start_point[0] + 1,
                        context_snippet=self._get_source_line(call_node, source),
                    )
                )

    # =========================================================================
    # Rake DSL Extraction
    # =========================================================================

    def _extract_rake_dsl(
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
    ) -> None:
        """Extract Rake task/namespace DSL constructs."""
        self._walk_rake_node(
            root,
            source,
            result,
            file_id,
            repo_id,
            module_name,
            namespace_stack=[],
            pending_desc=None,
        )

    def _walk_rake_node(
        self,
        node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        namespace_stack: list[str],
        pending_desc: str | None,
    ) -> None:
        """Recursively walk AST for Rake patterns."""
        for child in node.children:
            if child.type != "call":
                if child.type in ("do_block", "block", "body_statement", "program"):
                    self._walk_rake_node(
                        child,
                        source,
                        result,
                        file_id,
                        repo_id,
                        module_name,
                        namespace_stack,
                        pending_desc,
                    )
                continue

            method_node = self._find_child(child, "identifier")
            if not method_node:
                continue

            method_name = self._node_text(method_node, source)

            if method_name == "desc":
                pending_desc = self._get_call_description(child, source)
            elif method_name == "task":
                self._handle_rake_task(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    namespace_stack,
                    pending_desc,
                )
                pending_desc = None
            elif method_name == "namespace":
                self._handle_rake_namespace(
                    child,
                    source,
                    result,
                    file_id,
                    repo_id,
                    module_name,
                    namespace_stack,
                )
                pending_desc = None

    def _handle_rake_task(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        namespace_stack: list[str],
        desc: str | None,
    ) -> None:
        """Handle task :name as FunctionEntity with EntityType.TASK."""
        task_name = self._get_call_description(call_node, source)
        if not task_name:
            return

        qualified_name = ":".join([*namespace_stack, task_name]) if namespace_stack else task_name

        result.functions.append(
            FunctionEntity(
                id=uuid4(),
                name=task_name,
                qualified_name=qualified_name,
                entity_type=EntityType.TASK,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=call_node.start_point[0] + 1,
                line_end=call_node.end_point[0] + 1,
                language="ruby",
                parameters=[],
                return_type=None,
                is_async=False,
                decorators=[],
                docstring=desc,
            )
        )

    def _handle_rake_namespace(
        self,
        call_node: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
        module_name: str,
        namespace_stack: list[str],
    ) -> None:
        """Handle namespace :name as ModuleEntity."""
        ns_name = self._get_call_description(call_node, source)
        if not ns_name:
            return

        qualified_name = ":".join([*namespace_stack, ns_name]) if namespace_stack else ns_name

        result.modules.append(
            ModuleEntity(
                id=uuid4(),
                name=ns_name,
                qualified_name=qualified_name,
                entity_type=EntityType.MODULE,
                repository_id=repo_id,
                file_id=file_id,
                file_path=result.file_path,
                line_start=call_node.start_point[0] + 1,
                line_end=call_node.end_point[0] + 1,
                language="ruby",
            )
        )

        block = self._get_call_block(call_node)
        if block:
            self._walk_rake_node(
                block,
                source,
                result,
                file_id,
                repo_id,
                module_name,
                [*namespace_stack, ns_name],
                pending_desc=None,
            )

    # =========================================================================
    # Gemfile Extraction
    # =========================================================================

    def _extract_gemfile_deps(
        self,
        root: Node,
        source: bytes,
        result: ExtractionResult,
        file_id: UUID,
        repo_id: UUID,
    ) -> None:
        """Extract gem dependencies from Gemfile."""
        for call_node in self._find_descendants(root, "call"):
            method_node = self._find_child(call_node, "identifier")
            if not method_node:
                continue
            if self._node_text(method_node, source) != "gem":
                continue

            gem_name = self._get_call_description(call_node, source)
            if not gem_name:
                continue

            result.imports.append(
                ImportEntity(
                    id=uuid4(),
                    name=gem_name,
                    qualified_name=gem_name,
                    entity_type=EntityType.IMPORT,
                    repository_id=repo_id,
                    file_id=file_id,
                    file_path=result.file_path,
                    line_start=call_node.start_point[0] + 1,
                    line_end=call_node.end_point[0] + 1,
                    language="ruby",
                    source_module=gem_name,
                    imported_symbols=[gem_name],
                    is_relative=False,
                )
            )
