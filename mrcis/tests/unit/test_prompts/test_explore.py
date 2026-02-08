"""Tests for mrcis_explore prompt."""

from mrcis.prompts.explore import mrcis_explore


class TestMrcisExplore:
    """Test mrcis_explore prompt function."""

    def test_returns_list_of_messages(self) -> None:
        """Should return a list with exactly one message."""
        result = mrcis_explore(symbol_name="MyClass")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_message_has_user_role(self) -> None:
        """Should return a user-role message."""
        result = mrcis_explore(symbol_name="MyClass")
        msg = result[0]
        assert msg["role"] == "user"

    def test_symbol_name_interpolated(self) -> None:
        """Should interpolate symbol_name into the content."""
        result = mrcis_explore(symbol_name="mypackage.MyClass")
        content = result[0]["content"]
        assert "mypackage.MyClass" in content

    def test_without_repository_no_scoping_text(self) -> None:
        """Without repository arg, should not contain scoping text."""
        result = mrcis_explore(symbol_name="MyClass")
        content = result[0]["content"]
        assert "Scoping to repository" not in content

    def test_with_repository_includes_scoping(self) -> None:
        """With repository arg, should include scoping context."""
        result = mrcis_explore(symbol_name="MyClass", repository="my-repo")
        content = result[0]["content"]
        assert "Scoping to repository: my-repo" in content

    def test_with_repository_includes_repo_filter(self) -> None:
        """With repository arg, tool call params should include repository filter."""
        result = mrcis_explore(symbol_name="MyClass", repository="my-repo")
        content = result[0]["content"]
        assert 'repository: "my-repo"' in content

    def test_without_repository_no_repo_filter(self) -> None:
        """Without repository, tool call params should not include repository filter."""
        result = mrcis_explore(symbol_name="MyClass")
        content = result[0]["content"]
        # Should not have a repository filter line in the tool call params
        assert "- repository:" not in content

    def test_contains_workflow_sections(self) -> None:
        """Should contain the four workflow sections."""
        result = mrcis_explore(symbol_name="Foo")
        content = result[0]["content"]
        assert "## Workflow" in content
        assert "### 1. Create a task list" in content
        assert "### 2. Find the definition" in content
        assert "### 3. Map usage patterns" in content
        assert "### 4. Summarize findings" in content

    def test_contains_mrcis_tool_names(self) -> None:
        """Should reference the correct MRCIS tool names."""
        result = mrcis_explore(symbol_name="Foo")
        content = result[0]["content"]
        assert "mrcis_find_symbol" in content
        assert "mrcis_search_code" in content
        assert "mrcis_find_usages" in content
        assert "mrcis_get_references" in content

    def test_contains_risk_assessment(self) -> None:
        """Should contain the risk assessment section."""
        result = mrcis_explore(symbol_name="Foo")
        content = result[0]["content"]
        assert "Risk assessment" in content
        assert "HIGH" in content
        assert "MEDIUM" in content
        assert "LOW" in content
