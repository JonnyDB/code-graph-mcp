"""MCP prompts for cross-repository change safety workflows.

Prompts are reusable workflow templates that MCP clients discover via
prompts/list and invoke via prompts/get. They return structured messages
with explicit MRCIS tool call instructions.
"""

from mrcis.prompts.change_plan import mrcis_change_plan
from mrcis.prompts.explore import mrcis_explore
from mrcis.prompts.impact import mrcis_impact_analysis
from mrcis.prompts.safe_change import mrcis_safe_change

__all__ = [
    "mrcis_change_plan",
    "mrcis_explore",
    "mrcis_impact_analysis",
    "mrcis_safe_change",
]
