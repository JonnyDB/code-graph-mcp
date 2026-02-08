"""Tests for HTMLExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.html_extractor import HTMLExtractor


@pytest.fixture
def extractor():
    """Provide HTMLExtractor instance."""
    return HTMLExtractor()


@pytest.fixture
def write_html_file(tmp_path: Path):
    """Factory fixture to write HTML files."""

    def _write(content: str, ext: str = ".html") -> Path:
        file_path = tmp_path / f"test_page{ext}"
        file_path.write_text(content)
        return file_path

    return _write


class TestHTMLExtractorSupports:
    """Tests for file support detection."""

    def test_supports_html_files(self, extractor) -> None:
        """Test supports .html files."""
        assert extractor.supports(Path("index.html"))

    def test_supports_htm_files(self, extractor) -> None:
        """Test supports .htm files."""
        assert extractor.supports(Path("page.htm"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support other file types."""
        assert not extractor.supports(Path("style.css"))


class TestHTMLElementIDExtraction:
    """Tests for element ID extraction."""

    @pytest.mark.asyncio
    async def test_extract_element_ids(self, extractor, write_html_file) -> None:
        """Test extracting element IDs."""
        html = """
<html>
<body>
    <div id="header">Header</div>
    <div id="content">Content</div>
    <div id="footer">Footer</div>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert len(result.variables) >= 3
        id_names = [v.name for v in result.variables if v.qualified_name.startswith("id:")]
        assert "header" in id_names
        assert "content" in id_names
        assert "footer" in id_names

    @pytest.mark.asyncio
    async def test_extract_duplicate_ids(self, extractor, write_html_file) -> None:
        """Test handling duplicate IDs (should only extract once)."""
        html = """
<html>
<body>
    <div id="main">First</div>
    <div id="main">Duplicate</div>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        id_vars = [v for v in result.variables if v.qualified_name.startswith("id:")]
        # Both should be extracted as separate entities
        assert len(id_vars) == 2


class TestHTMLClassExtraction:
    """Tests for class extraction."""

    @pytest.mark.asyncio
    async def test_extract_classes(self, extractor, write_html_file) -> None:
        """Test extracting CSS classes."""
        html = """
<html>
<body>
    <div class="container">Container</div>
    <div class="row">Row</div>
    <div class="col-md-6">Column</div>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        class_names = [v.name for v in result.variables if v.qualified_name.startswith("class:")]
        assert "container" in class_names
        assert "row" in class_names
        assert "col-md-6" in class_names

    @pytest.mark.asyncio
    async def test_extract_multiple_classes(self, extractor, write_html_file) -> None:
        """Test extracting multiple classes from single element."""
        html = """
<html>
<body>
    <div class="btn btn-primary btn-lg">Button</div>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        class_names = [v.name for v in result.variables if v.qualified_name.startswith("class:")]
        assert "btn" in class_names
        assert "btn-primary" in class_names
        assert "btn-lg" in class_names


class TestHTMLScriptExtraction:
    """Tests for script reference extraction."""

    @pytest.mark.asyncio
    async def test_extract_script_src(self, extractor, write_html_file) -> None:
        """Test extracting script src attributes."""
        html = """
<html>
<head>
    <script src="jquery.min.js"></script>
    <script src="app.js"></script>
    <script src="https://cdn.example.com/lib.js"></script>
</head>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        script_refs = [v for v in result.variables if v.qualified_name.startswith("script:")]
        assert len(script_refs) == 3
        script_names = [v.name for v in script_refs]
        assert "jquery.min.js" in script_names
        assert "app.js" in script_names
        assert "https://cdn.example.com/lib.js" in script_names

    @pytest.mark.asyncio
    async def test_ignore_inline_scripts(self, extractor, write_html_file) -> None:
        """Test that inline scripts without src are ignored."""
        html = """
<html>
<head>
    <script>console.log("inline");</script>
    <script src="external.js"></script>
</head>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        script_refs = [v for v in result.variables if v.qualified_name.startswith("script:")]
        # Only external script should be extracted
        assert len(script_refs) == 1
        assert script_refs[0].name == "external.js"


class TestHTMLLinkExtraction:
    """Tests for link reference extraction."""

    @pytest.mark.asyncio
    async def test_extract_stylesheet_links(self, extractor, write_html_file) -> None:
        """Test extracting stylesheet link references."""
        html = """
<html>
<head>
    <link rel="stylesheet" href="styles.css">
    <link rel="stylesheet" href="theme.css">
    <link rel="icon" href="favicon.ico">
</head>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        link_refs = [v for v in result.variables if v.qualified_name.startswith("link:")]
        assert len(link_refs) == 3
        link_names = [v.name for v in link_refs]
        assert "styles.css" in link_names
        assert "theme.css" in link_names
        assert "favicon.ico" in link_names

    @pytest.mark.asyncio
    async def test_extract_anchor_hrefs(self, extractor, write_html_file) -> None:
        """Test extracting anchor href references."""
        html = """
<html>
<body>
    <a href="about.html">About</a>
    <a href="contact.html">Contact</a>
    <a href="https://example.com">External</a>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        link_refs = [v for v in result.variables if v.qualified_name.startswith("link:")]
        assert len(link_refs) >= 3
        link_names = [v.name for v in link_refs]
        assert "about.html" in link_names
        assert "contact.html" in link_names
        assert "https://example.com" in link_names


class TestHTMLDataAttributeExtraction:
    """Tests for data attribute extraction."""

    @pytest.mark.asyncio
    async def test_extract_data_attributes(self, extractor, write_html_file) -> None:
        """Test extracting data-* attributes."""
        html = """
<html>
<body>
    <div data-id="123" data-type="user" data-action="click">Element</div>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        data_attrs = [v for v in result.variables if v.qualified_name.startswith("data:")]
        assert len(data_attrs) == 3
        attr_names = [v.name for v in data_attrs]
        assert "data-id" in attr_names
        assert "data-type" in attr_names
        assert "data-action" in attr_names

    @pytest.mark.asyncio
    async def test_extract_multiple_data_attrs_same_name(self, extractor, write_html_file) -> None:
        """Test extracting same data attribute from multiple elements."""
        html = """
<html>
<body>
    <div data-role="button">Button 1</div>
    <div data-role="button">Button 2</div>
    <div data-role="link">Link</div>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        data_attrs = [v for v in result.variables if v.qualified_name.startswith("data:")]
        # All three elements should be tracked
        assert len(data_attrs) == 3


class TestHTMLComplexDocument:
    """Tests for complex HTML documents."""

    @pytest.mark.asyncio
    async def test_extract_full_page(self, extractor, write_html_file) -> None:
        """Test extracting from a complete HTML page."""
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <link rel="stylesheet" href="main.css">
    <script src="app.js"></script>
</head>
<body>
    <nav id="navbar" class="navbar navbar-expand">
        <a href="home.html">Home</a>
        <a href="about.html">About</a>
    </nav>
    <main id="content" class="container">
        <div data-component="card" data-id="1">
            <h1>Welcome</h1>
        </div>
    </main>
    <footer id="footer" class="footer">
        <p>&copy; 2024</p>
    </footer>
</body>
</html>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should extract various entities
        assert len(result.variables) > 0

        # Check for IDs
        id_names = [v.name for v in result.variables if v.qualified_name.startswith("id:")]
        assert "navbar" in id_names
        assert "content" in id_names
        assert "footer" in id_names

        # Check for classes
        class_names = [v.name for v in result.variables if v.qualified_name.startswith("class:")]
        assert "navbar" in class_names
        assert "container" in class_names
        assert "footer" in class_names

        # Check for references
        link_refs = [v.name for v in result.variables if v.qualified_name.startswith("link:")]
        assert "main.css" in link_refs
        assert "home.html" in link_refs

        script_refs = [v.name for v in result.variables if v.qualified_name.startswith("script:")]
        assert "app.js" in script_refs

        # Check for data attributes
        data_attrs = [v.name for v in result.variables if v.qualified_name.startswith("data:")]
        assert "data-component" in data_attrs
        assert "data-id" in data_attrs


class TestHTMLErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handle_malformed_html(self, extractor, write_html_file) -> None:
        """Test handling malformed HTML gracefully."""
        html = """
<html>
<body>
    <div id="test">Unclosed div
    <div class="another">Another div</div>
</body>
"""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        # Should still extract what it can
        assert len(result.variables) >= 2

    @pytest.mark.asyncio
    async def test_handle_empty_html(self, extractor, write_html_file) -> None:
        """Test handling empty HTML file."""
        html = ""
        file_path = write_html_file(html)
        result = await extractor.extract(file_path, uuid4(), uuid4())
        assert result.variables == []
        assert result.language == "html"
