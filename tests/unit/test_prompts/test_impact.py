"""Tests for mrcis_impact_analysis prompt."""

from mrcis.prompts.impact import mrcis_impact_analysis


class TestMrcisImpactAnalysis:
    """Test mrcis_impact_analysis prompt function."""

    def test_returns_list_of_messages(self) -> None:
        result = mrcis_impact_analysis(symbol_name="MyClass")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_message_has_user_role(self) -> None:
        result = mrcis_impact_analysis(symbol_name="MyClass")
        assert result[0]["role"] == "user"

    def test_symbol_name_interpolated(self) -> None:
        result = mrcis_impact_analysis(symbol_name="pkg.MyClass")
        content = result[0]["content"]
        assert "pkg.MyClass" in content

    def test_without_repository_no_scoping(self) -> None:
        result = mrcis_impact_analysis(symbol_name="MyClass")
        content = result[0]["content"]
        assert "Scoping to repository" not in content

    def test_with_repository_includes_scoping(self) -> None:
        result = mrcis_impact_analysis(symbol_name="MyClass", repository="my-repo")
        content = result[0]["content"]
        assert "Scoping to repository: my-repo" in content

    def test_contains_workflow_sections(self) -> None:
        result = mrcis_impact_analysis(symbol_name="Foo")
        content = result[0]["content"]
        assert "### 2. Resolve the symbol" in content
        assert "### 3. Find all direct dependents" in content
        assert "### 4. Analyze transitive impact" in content
        assert "### 5. Produce impact report" in content

    def test_contains_risk_levels(self) -> None:
        result = mrcis_impact_analysis(symbol_name="Foo")
        content = result[0]["content"]
        assert "CRITICAL" in content
        assert "HIGH" in content
        assert "MEDIUM" in content
        assert "LOW" in content

    def test_contains_mrcis_tool_names(self) -> None:
        result = mrcis_impact_analysis(symbol_name="Foo")
        content = result[0]["content"]
        assert "mrcis_find_symbol" in content
        assert "mrcis_get_references" in content
        assert "mrcis_find_usages" in content

    def test_mentions_transitive_analysis(self) -> None:
        result = mrcis_impact_analysis(symbol_name="Foo")
        content = result[0]["content"]
        assert "transitive" in content.lower()
        assert "second-order" in content.lower()
