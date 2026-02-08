"""MCP prompt: mrcis_explore — general-purpose symbol exploration."""

from typing import Any


def mrcis_explore(
    symbol_name: str,
    repository: str | None = None,
) -> list[dict[str, Any]]:
    """Explore a symbol: definition, usage patterns, and cross-repo relationships.

    Args:
        symbol_name: Simple or qualified name (e.g. MyClass or mypackage.module.MyClass).
        repository: Optional repository name to scope the search.

    Returns:
        List of MCP messages containing the exploration workflow.
    """
    repo_context = f"Scoping to repository: {repository}\n" if repository else ""
    repo_filter = f'- repository: "{repository}"\n' if repository else ""

    template = f"""\
You are investigating the symbol "{symbol_name}" using MRCIS code intelligence tools.
{repo_context}
## Workflow

### 1. Create a task list
Create tasks to track this exploration:
- Task 1: "Find definition of {symbol_name}"
- Task 2: "Map usage patterns of {symbol_name}"
- Task 3: "Trace cross-repo relationships of {symbol_name}"
- Task 4: "Summarize findings for {symbol_name}"

### 2. Find the definition (Task 1)
Mark Task 1 as in_progress.

Call `mrcis_find_symbol` with:
- qualified_name: "{symbol_name}"
- include_source: true

If not found (found=false), fall back to `mrcis_search_code` with:
- query: "{symbol_name}"
- limit: 5
{repo_filter}
Record the qualified_name from the result. Mark Task 1 as completed.

### 3. Map usage patterns and trace relationships (Tasks 2 & 3 — run in parallel)
Mark Tasks 2 and 3 as in_progress.

Launch two sub-agents in parallel:

**Sub-agent A (Task 2):** Call `mrcis_find_usages` with:
- symbol_name: <qualified_name from step 2>
{repo_filter}\
Report: list of files/repos that use this symbol, grouped by repository, with relation types.

**Sub-agent B (Task 3):** Call `mrcis_get_references` with:
- qualified_name: <qualified_name from step 2>
- include_outgoing: true
Report: incoming references (who depends on this symbol) and outgoing references \
(what this symbol depends on), with cross-repo relationships highlighted.

Mark Tasks 2 and 3 as completed when sub-agents return.

### 4. Summarize findings (Task 4)
Mark Task 4 as in_progress.

Synthesize results from all prior steps into a structured summary:

**Definition:**
- Type, signature, file path, repository, line range
- Source code snippet (first 20 lines if long)

**Cross-repo footprint:**
- Repositories that use this symbol (list with counts)
- How each repo uses it (imports, calls, extends, implements)

**Dependency graph:**
- Incoming: N symbols across M repos depend on this
- Outgoing: This symbol depends on N other symbols

**Risk assessment:**
- HIGH if used across 3+ repos or has 10+ incoming references
- MEDIUM if used across 2 repos or has 3-9 incoming references
- LOW if used within 1 repo with <3 incoming references

Mark Task 4 as completed."""

    return [{"role": "user", "content": template}]
