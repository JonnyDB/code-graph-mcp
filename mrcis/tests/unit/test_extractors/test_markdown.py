"""Tests for MarkdownExtractor."""

from pathlib import Path
from uuid import uuid4

import pytest

from mrcis.extractors.markdown import MarkdownExtractor


@pytest.fixture
def extractor():
    """Provide MarkdownExtractor instance."""
    return MarkdownExtractor()


@pytest.fixture
def write_md_file(tmp_path: Path):
    """Factory fixture to write Markdown files."""

    def _write(content: str, ext: str = ".md") -> Path:
        file_path = tmp_path / f"test_doc{ext}"
        file_path.write_text(content)
        return file_path

    return _write


class TestMarkdownExtractorSupports:
    """Tests for file support detection."""

    def test_supports_md_files(self, extractor) -> None:
        """Test supports .md files."""
        assert extractor.supports(Path("README.md"))
        assert extractor.supports(Path("doc.MD"))

    def test_supports_markdown_files(self, extractor) -> None:
        """Test supports .markdown files."""
        assert extractor.supports(Path("doc.markdown"))

    def test_does_not_support_other_files(self, extractor) -> None:
        """Test doesn't support non-Markdown files."""
        assert not extractor.supports(Path("doc.txt"))
        assert not extractor.supports(Path("doc.html"))


class TestMarkdownHeadingExtraction:
    """Tests for heading extraction."""

    @pytest.mark.asyncio
    async def test_extract_h1_heading(self, extractor, write_md_file) -> None:
        """Test extracting H1 heading."""
        code = "# Introduction\n\nSome content here."
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        assert len(result.variables) >= 1
        heading = next((v for v in result.variables if v.name == "Introduction"), None)
        assert heading is not None
        assert heading.qualified_name == "Introduction"

    @pytest.mark.asyncio
    async def test_extract_multiple_headings(self, extractor, write_md_file) -> None:
        """Test extracting multiple headings at different levels."""
        code = """# Title
## Section 1
### Subsection 1.1
## Section 2
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should extract all headings
        headings = [v for v in result.variables if "Title" in v.name or "Section" in v.name]
        assert len(headings) >= 3

    @pytest.mark.asyncio
    async def test_extract_nested_heading_hierarchy(self, extractor, write_md_file) -> None:
        """Test hierarchical heading structure."""
        code = """# Main Title
## Overview
### Details
## Installation
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Check that Overview shows proper nesting
        overview = next(
            (v for v in result.variables if v.name == "Overview"),
            None,
        )
        assert overview is not None
        assert "Main Title.Overview" in overview.qualified_name


class TestMarkdownCodeBlockExtraction:
    """Tests for code block extraction."""

    @pytest.mark.asyncio
    async def test_extract_fenced_code_block(self, extractor, write_md_file) -> None:
        """Test extracting fenced code block."""
        code = """# Example

```python
def hello():
    print("Hello, World!")
```
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Code blocks should be in variables
        code_blocks = [v for v in result.variables if "code_block" in v.name]
        assert len(code_blocks) >= 1

    @pytest.mark.asyncio
    async def test_extract_code_block_with_language(self, extractor, write_md_file) -> None:
        """Test extracting code block with language tag."""
        code = """```javascript
const greeting = "Hello!";
console.log(greeting);
```
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        code_blocks = [v for v in result.variables if "code_block" in v.name]
        assert len(code_blocks) >= 1
        # Language info should be in annotations or docstring
        block = code_blocks[0]
        assert (
            "javascript" in (block.docstring or "").lower()
            or "javascript" in str(block.annotations).lower()
        )

    @pytest.mark.asyncio
    async def test_extract_multiple_code_blocks(self, extractor, write_md_file) -> None:
        """Test extracting multiple code blocks."""
        code = """# Examples

Python example:
```python
x = 42
```

JavaScript example:
```javascript
const x = 42;
```
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        code_blocks = [v for v in result.variables if "code_block" in v.name]
        assert len(code_blocks) >= 2


class TestMarkdownLinkExtraction:
    """Tests for link extraction."""

    @pytest.mark.asyncio
    async def test_extract_inline_link(self, extractor, write_md_file) -> None:
        """Test extracting inline link."""
        code = "Check out [OpenAI](https://openai.com) for more info."
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Links should be in imports or variables
        links = [i for i in result.imports if "openai.com" in i.source_module or "OpenAI" in i.name]
        assert len(links) >= 1

    @pytest.mark.asyncio
    async def test_extract_reference_link(self, extractor, write_md_file) -> None:
        """Test extracting reference-style link."""
        code = """Check [this][ref] out.

[ref]: https://example.com "Example"
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should extract reference link
        links = [i for i in result.imports if "example.com" in i.source_module]
        assert len(links) >= 1

    @pytest.mark.asyncio
    async def test_extract_relative_link(self, extractor, write_md_file) -> None:
        """Test extracting relative documentation link."""
        code = "See [Installation Guide](./docs/install.md) for setup."
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Relative links should be marked as such
        rel_links = [i for i in result.imports if i.is_relative]
        assert len(rel_links) >= 1


class TestMarkdownComplexDocument:
    """Tests for complex Markdown documents."""

    @pytest.mark.asyncio
    async def test_extract_full_readme(self, extractor, write_md_file) -> None:
        """Test extracting from a realistic README."""
        code = """# Project Name

[![Build Status](https://travis-ci.org/user/project.svg)](https://travis-ci.org/user/project)

## Installation

Install via npm:

```bash
npm install project
```

## Usage

Basic example:

```javascript
import { feature } from 'project';

feature.doSomething();
```

## Documentation

See [API Docs](./docs/api.md) for details.

## License

MIT - see [LICENSE](./LICENSE) file.
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should extract headings
        headings = [
            v
            for v in result.variables
            if any(
                name in v.name
                for name in ["Project Name", "Installation", "Usage", "Documentation"]
            )
        ]
        assert len(headings) >= 2

        # Should extract code blocks
        code_blocks = [v for v in result.variables if "code_block" in v.name]
        assert len(code_blocks) >= 1

        # Should extract links
        assert len(result.imports) >= 1

    @pytest.mark.asyncio
    async def test_extract_empty_markdown(self, extractor, write_md_file) -> None:
        """Test extracting from empty Markdown file."""
        code = ""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should not crash, just return empty results
        assert result.file_path == str(file_path)
        assert result.language == "markdown"

    @pytest.mark.asyncio
    async def test_extract_markdown_with_html(self, extractor, write_md_file) -> None:
        """Test extracting Markdown with embedded HTML."""
        code = """# Title

<div class="alert">
Important notice!
</div>

Regular markdown content.
"""
        file_path = write_md_file(code)

        result = await extractor.extract(file_path, uuid4(), uuid4())

        # Should extract at least the title
        headings = [v for v in result.variables if "Title" in v.name]
        assert len(headings) >= 1
