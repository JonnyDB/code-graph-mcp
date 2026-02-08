"""MCP prompt: mrcis_impact_analysis — pre-change impact analysis."""

from typing import Any


def mrcis_impact_analysis(
    symbol_name: str,
    repository: str | None = None,
) -> list[dict[str, Any]]:
    """Analyze what breaks if a symbol is changed.

    Args:
        symbol_name: Simple or qualified name.
        repository: Optional repository name to scope the search.

    Returns:
        List of MCP messages containing the impact analysis workflow.
    """
    repo_context = f"Scoping to repository: {repository}\n" if repository else ""

    template = f"""\
You are performing an impact analysis for the symbol "{symbol_name}" using MRCIS code \
intelligence tools. The goal is to identify every symbol across all indexed repositories \
that would be affected by a change to "{symbol_name}".
{repo_context}
## Workflow

### 1. Create a task list
- Task 1: "Resolve symbol definition for {symbol_name}"
- Task 2: "Find direct dependents of {symbol_name}"
- Task 3: "Analyze transitive impact of {symbol_name}"
- Task 4: "Produce impact report for {symbol_name}"

### 2. Resolve the symbol (Task 1)
Mark Task 1 as in_progress.

Call `mrcis_find_symbol` with:
- qualified_name: "{symbol_name}"
- include_source: true

Record: qualified_name, entity_type, signature, repository, file_path.
If the symbol is a class, note its base_classes and whether it is_exported.
If not found, fall back to `mrcis_search_code` with query: "{symbol_name}", limit: 5.
Mark Task 1 as completed.

### 3. Find all direct dependents (Task 2)
Mark Task 2 as in_progress.

Launch two sub-agents in parallel:

**Sub-agent A — Incoming references:**
Call `mrcis_get_references` with:
- qualified_name: <qualified_name>
- include_outgoing: false
Collect all incoming references. Group by:
- repository (cross-repo vs same-repo)
- relation_type (calls, imports, extends, implements, instantiates, uses_type, references)

**Sub-agent B — Usage search:**
Call `mrcis_find_usages` with:
- symbol_name: <simple_name from qualified_name>
(no repository filter — search ALL repos)
This catches references that may not have resolved relations yet (pending references).

Merge results from both sub-agents, deduplicating by file_path + line_number.
Mark Task 2 as completed.

### 4. Analyze transitive impact (Task 3)
Mark Task 3 as in_progress.

For each CROSS-REPO dependent found in Task 2 that is itself exported or public:
Launch a sub-agent to call `mrcis_get_references` with:
- qualified_name: <dependent's qualified_name>
- include_outgoing: false

This finds second-order dependents — symbols that depend on symbols that depend on the target.
Limit to 1 level of transitivity to avoid explosion.
Mark Task 3 as completed.

### 5. Produce impact report (Task 4)
Mark Task 4 as in_progress.

Structure the report as:

**Symbol under analysis:**
- qualified_name, entity_type, signature, repository, file_path, lines

**Direct dependents (first-order):**
For each affected repository:
  - Repository name
  - Number of affected symbols
  - Affected symbols list: qualified_name, relation_type, file_path, line_number
  - Whether the dependent is exported (propagation risk)

**Transitive dependents (second-order):**
Same structure as above, indented under the first-order dependent that links them.

**Impact summary:**
- Total repositories affected: N
- Total symbols affected: N (direct) + N (transitive)
- Cross-repo relations: N
- Highest-risk relation types found: (extends/implements are highest risk, calls is medium, \
imports is lower)

**Risk level:**
- CRITICAL: Symbol is extended/implemented across repos (interface contract)
- HIGH: Symbol is called from 3+ repos or has 10+ cross-repo dependents
- MEDIUM: Symbol is used across 2 repos or has 3-9 cross-repo dependents
- LOW: Symbol is used within 1 repo only

Mark Task 4 as completed."""

    return [{"role": "user", "content": template}]
