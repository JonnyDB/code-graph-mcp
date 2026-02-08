"""HTML file extractor."""

from html.parser import HTMLParser
from pathlib import Path
from uuid import UUID, uuid4

from mrcis.models.entities import EntityType, VariableEntity
from mrcis.models.extraction import ExtractionResult


class HTMLDataExtractor(HTMLParser):
    """Custom HTML parser to extract IDs, classes, and references."""

    def __init__(self) -> None:
        """Initialize parser."""
        super().__init__()
        self.ids: list[str] = []
        self.classes: list[str] = []
        self.scripts: list[str] = []
        self.links: list[str] = []
        self.data_attrs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle opening tags and extract relevant attributes."""
        attr_dict = dict(attrs)

        # Extract ID attribute
        element_id = attr_dict.get("id")
        if element_id:
            self.ids.append(element_id)

        # Extract class attribute (can have multiple classes)
        class_attr = attr_dict.get("class")
        if class_attr:
            classes = class_attr.split()
            self.classes.extend(classes)

        # Extract script src
        if tag == "script" and "src" in attr_dict and attr_dict["src"]:
            self.scripts.append(attr_dict["src"])

        # Extract link href (stylesheets, icons, etc.)
        if tag == "link" and "href" in attr_dict and attr_dict["href"]:
            self.links.append(attr_dict["href"])

        # Extract anchor href
        if tag == "a" and "href" in attr_dict and attr_dict["href"]:
            href = attr_dict["href"]
            # Skip fragment-only links and javascript: links
            if href and not href.startswith("#") and not href.startswith("javascript:"):
                self.links.append(href)

        # Extract data-* attributes
        for attr_name, attr_value in attrs:
            if attr_name.startswith("data-") and attr_value:
                self.data_attrs.append(attr_name)


class HTMLExtractor:
    """Extractor for HTML markup files."""

    def get_supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {".html", ".htm"}

    def supports(self, file_path: Path) -> bool:
        """Check if this extractor supports the file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    async def extract(self, file_path: Path, file_id: UUID, repo_id: UUID) -> ExtractionResult:
        """Extract entities from HTML file."""
        result = ExtractionResult(
            file_id=file_id,
            file_path=str(file_path),
            repository_id=repo_id,
            language="html",
        )

        try:
            content = file_path.read_text(encoding="utf-8")
            parser = HTMLDataExtractor()
            parser.feed(content)

            # Extract IDs as variables
            for element_id in parser.ids:
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=element_id,
                        qualified_name=f"id:{element_id}",
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=1,
                        line_end=1,
                        language="html",
                    )
                )

            # Extract classes as variables
            for css_class in parser.classes:
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=css_class,
                        qualified_name=f"class:{css_class}",
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=1,
                        line_end=1,
                        language="html",
                    )
                )

            # Extract script references as variables
            for script in parser.scripts:
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=script,
                        qualified_name=f"script:{script}",
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=1,
                        line_end=1,
                        language="html",
                    )
                )

            # Extract link references as variables
            for link in parser.links:
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=link,
                        qualified_name=f"link:{link}",
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=1,
                        line_end=1,
                        language="html",
                    )
                )

            # Extract data-* attributes as variables
            for data_attr in parser.data_attrs:
                result.variables.append(
                    VariableEntity(
                        id=uuid4(),
                        name=data_attr,
                        qualified_name=f"data:{data_attr}",
                        entity_type=EntityType.VARIABLE,
                        repository_id=repo_id,
                        file_id=file_id,
                        file_path=str(file_path),
                        line_start=1,
                        line_end=1,
                        language="html",
                    )
                )

        except Exception as e:
            result.parse_errors.append(f"HTML parse error: {e}")

        return result
