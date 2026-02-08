"""Tests for prompt registration on the FastMCP server."""

from unittest.mock import MagicMock

from mrcis.server import create_server


def _make_mock_runtime():
    """Create a mock ServerRuntime for create_server()."""
    runtime = MagicMock()
    runtime.get_context.return_value = MagicMock()
    return runtime


class TestPromptRegistration:
    """Test that all prompts are registered on the MCP server."""

    def test_server_has_explore_prompt(self) -> None:
        """mrcis_explore should be registered."""
        server = create_server(_make_mock_runtime())
        prompts = server._prompt_manager._prompts
        assert "mrcis_explore" in prompts

    def test_server_has_impact_analysis_prompt(self) -> None:
        """mrcis_impact_analysis should be registered."""
        server = create_server(_make_mock_runtime())
        prompts = server._prompt_manager._prompts
        assert "mrcis_impact_analysis" in prompts

    def test_server_has_change_plan_prompt(self) -> None:
        """mrcis_change_plan should be registered."""
        server = create_server(_make_mock_runtime())
        prompts = server._prompt_manager._prompts
        assert "mrcis_change_plan" in prompts

    def test_server_has_safe_change_prompt(self) -> None:
        """mrcis_safe_change should be registered."""
        server = create_server(_make_mock_runtime())
        prompts = server._prompt_manager._prompts
        assert "mrcis_safe_change" in prompts

    def test_explore_prompt_has_required_args(self) -> None:
        """mrcis_explore should require symbol_name."""
        server = create_server(_make_mock_runtime())
        prompt = server._prompt_manager._prompts["mrcis_explore"]
        arg_names = [a.name for a in prompt.arguments]
        assert "symbol_name" in arg_names

    def test_safe_change_prompt_has_required_args(self) -> None:
        """mrcis_safe_change should require symbol_name and change_description."""
        server = create_server(_make_mock_runtime())
        prompt = server._prompt_manager._prompts["mrcis_safe_change"]
        arg_names = [a.name for a in prompt.arguments]
        assert "symbol_name" in arg_names
        assert "change_description" in arg_names

    def test_total_prompt_count(self) -> None:
        """Server should have exactly 4 prompts registered."""
        server = create_server(_make_mock_runtime())
        prompts = server._prompt_manager._prompts
        assert len(prompts) == 4
