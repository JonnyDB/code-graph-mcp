"""MCP prompt: mrcis_change_plan — file-by-file change plan for a proposed modification."""

from typing import Any


def mrcis_change_plan(
    symbol_name: str,
    change_description: str,
) -> list[dict[str, Any]]:
    """Create a cross-repository change plan for modifying a symbol.

    Args:
        symbol_name: Simple or qualified name.
        change_description: Natural language description of the proposed change.

    Returns:
        List of MCP messages containing the change plan workflow.
    """
    template = f"""\
You are creating a cross-repository change plan for modifying "{symbol_name}".
Proposed change: {change_description}

Use the MRCIS code intelligence tools to build a safe, ordered change plan.

## Workflow

### 1. Create a task list
- Task 1: "Analyze {symbol_name} definition and signature"
- Task 2: "Run impact analysis for {symbol_name}"
- Task 3: "Classify affected symbols by change type"
- Task 4: "Produce ordered change plan"

### 2. Analyze the symbol (Task 1)
Mark Task 1 as in_progress.

Call `mrcis_find_symbol` with:
- qualified_name: "{symbol_name}"
- include_source: true

Record the current: signature, parameters, return_type, base_classes, entity_type, repository.
This is the "before" state for diff analysis.
Mark Task 1 as completed.

### 3. Run full impact analysis (Task 2)
Mark Task 2 as in_progress.

Launch two sub-agents in parallel:

**Sub-agent A — Direct dependents:**
Call `mrcis_get_references` with:
- qualified_name: <qualified_name>
- include_outgoing: false
Group results by repository and relation_type.

**Sub-agent B — Usage search (catches unresolved refs):**
Call `mrcis_find_usages` with:
- symbol_name: <simple_name>
Group results by repository.

Merge and deduplicate results. Mark Task 2 as completed.

### 4. Classify each affected symbol (Task 3)
Mark Task 3 as in_progress.

For each dependent symbol, classify the required change based on relation_type \
and the proposed change:

| Relation Type | Change Classification |
|---|---|
| `extends` / `implements` | BREAKING — Subclass/implementor must be updated to match new contract |
| `overrides` | BREAKING — Override must match new signature |
| `calls` | REQUIRES_UPDATE if parameters/return_type changed; VERIFY_ONLY if just internal \
behavior changed |
| `imports` | REQUIRES_UPDATE if symbol renamed; NO_CHANGE if only behavior changed |
| `instantiates` | REQUIRES_UPDATE if constructor parameters changed |
| `uses_type` | REQUIRES_UPDATE if type shape changed; VERIFY_ONLY otherwise |
| `references` | VERIFY_ONLY — check that reference still makes sense |

For each symbol requiring update (BREAKING or REQUIRES_UPDATE), launch a sub-agent to:
Call `mrcis_find_symbol` with:
- qualified_name: <dependent's qualified_name>
- include_source: true
This retrieves the current source code the agent will need to modify.

Mark Task 3 as completed.

### 5. Produce ordered change plan (Task 4)
Mark Task 4 as in_progress.

Generate the plan in this format:

**Proposed change:** {change_description}
**Target symbol:** {symbol_name} in <repository>/<file_path>

**Change order** (execute in this sequence):

**Phase 1 — Update the source symbol:**
- File: <file_path> in <repository>
- Change: <specific modification based on change_description>

**Phase 2 — Update BREAKING dependents (extends/implements/overrides):**
For each, list:
- File: <file_path> in <repository>
- Symbol: <qualified_name>
- Relation: <relation_type>
- Required change: <specific modification>
- Current source: <snippet>

**Phase 3 — Update REQUIRES_UPDATE dependents (calls/imports/instantiates/uses_type):**
Same format as Phase 2.

**Phase 4 — Verify VERIFY_ONLY dependents:**
List files that need manual review but likely no code changes:
- File: <file_path> in <repository>
- Symbol: <qualified_name>
- Why verify: <reason>

**Verification steps:**
After all changes:
1. Run tests in each affected repository
2. Call `mrcis_reindex_repository` for each modified repository
3. Re-run `mrcis_get_references` on the modified symbol to confirm no broken references remain

Mark Task 4 as completed."""

    return [{"role": "user", "content": template}]
