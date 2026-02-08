"""Tests for mrcis_change_plan prompt."""

from mrcis.prompts.change_plan import mrcis_change_plan


class TestMrcisChangePlan:
    """Test mrcis_change_plan prompt function."""

    def test_returns_list_of_messages(self) -> None:
        result = mrcis_change_plan(symbol_name="MyClass", change_description="rename to NewClass")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_message_has_user_role(self) -> None:
        result = mrcis_change_plan(symbol_name="MyClass", change_description="rename to NewClass")
        assert result[0]["role"] == "user"

    def test_symbol_name_interpolated(self) -> None:
        result = mrcis_change_plan(
            symbol_name="pkg.MyClass", change_description="add timeout param"
        )
        content = result[0]["content"]
        assert "pkg.MyClass" in content

    def test_change_description_interpolated(self) -> None:
        result = mrcis_change_plan(symbol_name="MyClass", change_description="rename to NewClass")
        content = result[0]["content"]
        assert "rename to NewClass" in content

    def test_contains_workflow_sections(self) -> None:
        result = mrcis_change_plan(symbol_name="Foo", change_description="change return type")
        content = result[0]["content"]
        assert "### 2. Analyze the symbol" in content
        assert "### 3. Run full impact analysis" in content
        assert "### 4. Classify each affected symbol" in content
        assert "### 5. Produce ordered change plan" in content

    def test_contains_change_classification(self) -> None:
        result = mrcis_change_plan(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "BREAKING" in content
        assert "REQUIRES_UPDATE" in content
        assert "VERIFY_ONLY" in content

    def test_contains_phase_ordering(self) -> None:
        result = mrcis_change_plan(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "Phase 1" in content
        assert "Phase 2" in content
        assert "Phase 3" in content
        assert "Phase 4" in content

    def test_contains_verification_steps(self) -> None:
        result = mrcis_change_plan(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "Verification steps" in content
        assert "mrcis_reindex_repository" in content

    def test_contains_mrcis_tool_names(self) -> None:
        result = mrcis_change_plan(symbol_name="Foo", change_description="rename")
        content = result[0]["content"]
        assert "mrcis_find_symbol" in content
        assert "mrcis_get_references" in content
        assert "mrcis_find_usages" in content
