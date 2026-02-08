"""Tests for mrcis_safe_change prompt."""

from mrcis.prompts.safe_change import mrcis_safe_change


class TestMrcisSafeChange:
    """Test mrcis_safe_change prompt function."""

    def test_returns_list_of_messages(self) -> None:
        result = mrcis_safe_change(symbol_name="MyClass", change_description="rename to NewClass")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_message_has_user_role(self) -> None:
        result = mrcis_safe_change(symbol_name="MyClass", change_description="rename to NewClass")
        assert result[0]["role"] == "user"

    def test_symbol_name_interpolated(self) -> None:
        result = mrcis_safe_change(symbol_name="pkg.MyClass", change_description="add timeout")
        content = result[0]["content"]
        assert "pkg.MyClass" in content

    def test_change_description_interpolated(self) -> None:
        result = mrcis_safe_change(symbol_name="MyClass", change_description="rename to NewClass")
        content = result[0]["content"]
        assert "rename to NewClass" in content

    def test_without_repository_no_scoping(self) -> None:
        result = mrcis_safe_change(symbol_name="MyClass", change_description="rename")
        content = result[0]["content"]
        assert "Scoping to repository" not in content

    def test_with_repository_includes_scoping(self) -> None:
        result = mrcis_safe_change(
            symbol_name="MyClass",
            change_description="rename",
            repository="my-repo",
        )
        content = result[0]["content"]
        assert "Scoping to repository: my-repo" in content

    def test_contains_all_four_phases(self) -> None:
        result = mrcis_safe_change(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "## Phase 1: Explore the symbol" in content
        assert "## Phase 2: Impact analysis" in content
        assert "## Phase 3: Build change plan" in content
        assert "## Phase 4: Verification plan" in content

    def test_contains_gate_checks(self) -> None:
        result = mrcis_safe_change(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "### Gate check" in content
        assert "Symbol not found" in content
        assert "no dependents" in content.lower() or "0 incoming references" in content

    def test_contains_risk_levels(self) -> None:
        result = mrcis_safe_change(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "CRITICAL" in content
        assert "HIGH" in content
        assert "MEDIUM" in content
        assert "LOW" in content

    def test_contains_mrcis_tool_names(self) -> None:
        result = mrcis_safe_change(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "mrcis_find_symbol" in content
        assert "mrcis_get_references" in content
        assert "mrcis_find_usages" in content
        assert "mrcis_search_code" in content
        assert "mrcis_reindex_repository" in content

    def test_with_repository_includes_repo_filter_in_search(self) -> None:
        result = mrcis_safe_change(
            symbol_name="Foo",
            change_description="rename",
            repository="my-repo",
        )
        content = result[0]["content"]
        assert 'repository: "my-repo"' in content
