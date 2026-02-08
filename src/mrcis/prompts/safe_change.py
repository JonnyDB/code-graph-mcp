"""MCP prompt: mrcis_safe_change — meta-orchestration for safe cross-repo changes."""

from typing import Any


def mrcis_safe_change(
    symbol_name: str,
    change_description: str,
    repository: str | None = None,
) -> list[dict[str, Any]]:
    """Full safe change workflow: explore, impact analysis, change plan, and verification.

    Args:
        symbol_name: Simple or qualified name.
        change_description: Natural language description of the proposed change.
        repository: Optional repository name to scope initial search.

    Returns:
        List of MCP messages containing the full safe change workflow.
    """
    repo_context = f"Scoping to repository: {repository}\n" if repository else ""
    repo_filter = f', repository: "{repository}"' if repository else ""

    template = f"""\
You are performing a safe cross-repository change workflow for "{symbol_name}".
Proposed change: {change_description}
{repo_context}
This is a multi-phase workflow. Use task lists to track progress and sub-agents to \
parallelize independent work.

## Phase 1: Explore the symbol

### Create task list
- Task 1: "Find definition of {symbol_name}"
- Task 2: "Map usage patterns of {symbol_name}"
- Task 3: "Trace cross-repo relationships of {symbol_name}"

### Execute
**Task 1:** Call `mrcis_find_symbol` with qualified_name: "{symbol_name}", include_source: true.
If not found, call `mrcis_search_code` with query: "{symbol_name}", limit: 5{repo_filter}.
Record: qualified_name, entity_type, signature, repository, file_path, parameters, \
return_type, base_classes.

**Tasks 2 & 3 (parallel sub-agents):**
- Sub-agent A: Call `mrcis_find_usages` with symbol_name: <qualified_name>.
- Sub-agent B: Call `mrcis_get_references` with qualified_name: <qualified_name>, \
include_outgoing: true.

### Gate check
If the symbol is not found in any repository, STOP and report: \
"Symbol not found. Cannot proceed with change plan."
If the symbol has 0 incoming references and 0 usages, report: \
"Symbol has no dependents. Safe to modify directly." and skip to Phase 4.

## Phase 2: Impact analysis

### Add tasks
- Task 4: "Analyze transitive impact of {symbol_name}"
- Task 5: "Classify affected symbols"

### Execute
**Task 4:** For each cross-repo, exported dependent found in Phase 1:
Launch sub-agents to call `mrcis_get_references` with qualified_name: <dependent>, \
include_outgoing: false.
Collect second-order dependents. Limit to 1 level of transitivity.

**Task 5:** Classify each dependent by required change:
- BREAKING: extends, implements, overrides
- REQUIRES_UPDATE: calls (if signature changed), imports (if renamed), instantiates \
(if constructor changed), uses_type (if shape changed)
- VERIFY_ONLY: calls (if only behavior changed), references

### Gate check
Report impact summary:
- Total repos affected: N
- Total symbols: N direct + N transitive
- Risk level: CRITICAL / HIGH / MEDIUM / LOW

If risk is CRITICAL (interface contract broken across 3+ repos):
Report: "CRITICAL: This change breaks interface contracts across N repositories. \
Proceed with extreme caution."

## Phase 3: Build change plan

### Add tasks
- Task 6: "Fetch source for symbols requiring modification"
- Task 7: "Produce ordered change plan"

### Execute
**Task 6:** For each BREAKING and REQUIRES_UPDATE dependent:
Launch sub-agents to call `mrcis_find_symbol` with qualified_name: <dependent>, \
include_source: true.

**Task 7:** Produce the plan:

**Change order:**

1. **Source symbol** — <repository>/<file_path>
   - Change: <specific modification>

2. **BREAKING dependents** (must update to maintain contract):
   For each: repository, file_path, qualified_name, relation_type, required change, \
current source snippet.

3. **REQUIRES_UPDATE dependents** (must update call sites):
   Same format.

4. **VERIFY_ONLY dependents** (review, likely no change needed):
   File list with reason for review.

## Phase 4: Verification plan

### Add task
- Task 8: "Define verification steps"

### Execute
After all code changes are made:
1. Run test suites in each affected repository (list them).
2. Call `mrcis_reindex_repository` for each modified repository to update the index.
3. Call `mrcis_get_references` on "{symbol_name}" to confirm 0 broken references.
4. For each BREAKING dependent, call `mrcis_find_symbol` to confirm signatures are consistent.

Report: "Change plan complete. N files across M repositories need modification. \
Verification steps defined.\""""

    return [{"role": "user", "content": template}]
