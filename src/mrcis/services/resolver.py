"""Reference resolver service for cross-repository symbol resolution.

Runs periodically to match unresolved references against
newly indexed symbols.
"""

import asyncio
import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from loguru import logger

from mrcis.models.entities import EntityType

if TYPE_CHECKING:
    from mrcis.ports import RelationGraphPort


class EntityLike(Protocol):
    """Protocol for entity-like objects."""

    id: str
    qualified_name: str
    repository_id: str
    entity_type: EntityType


@dataclass
class ResolutionResult:
    """Result of a resolution batch."""

    resolved: int = 0
    unresolved: int = 0
    still_pending: int = 0


class ReferenceResolver:
    """
    Resolves pending cross-repository references.

    Runs periodically to match unresolved references
    against newly indexed symbols.
    """

    def __init__(
        self,
        relation_graph: "RelationGraphPort",
        interval_seconds: int = 60,
        max_attempts: int = 3,
    ) -> None:
        """Initialize resolver with relation graph port."""
        self.graph = relation_graph
        self.interval = interval_seconds
        self.max_attempts = max_attempts
        self._shutdown_event = asyncio.Event()

    async def run_forever(self) -> None:
        """Main resolution loop."""
        logger.info("Reference resolver started: interval={}s", self.interval)

        while not self._shutdown_event.is_set():
            try:
                result = await self.resolve_batch()
                if result.resolved > 0 or result.unresolved > 0:
                    logger.info(
                        "Resolution complete: resolved={} unresolved={} pending={}",
                        result.resolved,
                        result.unresolved,
                        result.still_pending,
                    )
            except Exception as e:
                logger.error("Resolution error: {}", e)

            # Wait for next interval or shutdown
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.interval)

    async def stop(self) -> None:
        """Signal shutdown."""
        self._shutdown_event.set()

    async def resolve_batch(self) -> ResolutionResult:
        """Attempt to resolve all pending references."""
        pending = await self.graph.get_pending_references(limit=100)

        result = ResolutionResult()

        for ref in pending:
            target = await self._find_target(
                ref.target_qualified_name,
                source_repository_id=ref.source_repository_id,
                relation_type=ref.relation_type,
                receiver_expr=ref.receiver_expr,
            )

            if target:
                # Resolve reference and create relation in one call
                await self.graph.resolve_reference(ref.id, target.id)
                result.resolved += 1
            else:
                # Increment attempts, mark unresolved if max reached
                await self.graph.mark_reference_unresolved(ref.id, max_attempts=self.max_attempts)
                if ref.attempts + 1 >= self.max_attempts:
                    result.unresolved += 1
                else:
                    result.still_pending += 1

        return result

    async def _find_target(
        self,
        pattern: str,
        source_repository_id: str | UUID,
        relation_type: str | None = None,
        receiver_expr: str | None = None,
    ) -> EntityLike | None:
        """
        Find a symbol matching the pattern.

        Supports:
        - Exact match: "sdk.validators.BaseValidator"
        - Suffix match: "*.BaseValidator" or just "BaseValidator"
        - Receiver-aware disambiguation for method calls
        """
        # Try exact match first
        exact = await self.graph.get_entity_by_qualified_name(pattern)
        if exact:
            return exact  # type: ignore[return-value]  # CodeEntity has UUID id, EntityLike expects str

        # Try suffix match
        if pattern.startswith("*."):
            suffix = pattern[2:]
        elif "." not in pattern:
            suffix = pattern
        else:
            # For dotted names like "mrcis.utils.paths.GitignoreFilter",
            # extract the simple name for suffix matching
            suffix = pattern.rsplit(".", 1)[-1]

        candidates = await self.graph.get_entities_by_suffix(suffix)

        # Filter by receiver context if available and multiple candidates
        if receiver_expr and len(candidates) > 1:
            matched_candidates = [
                c
                for c in candidates
                if self._matches_receiver_context(c.qualified_name, receiver_expr)
            ]
            # Only apply filter if at least one candidate matches
            # If no matches, better to leave unresolved than pick wrong one
            if matched_candidates:
                candidates = matched_candidates
            else:
                # No candidates match receiver - skip resolution
                logger.debug(
                    "No candidates match receiver context: receiver={} candidates={}",
                    receiver_expr,
                    [c.qualified_name for c in candidates],
                )
                return None

        if len(candidates) == 1:
            return candidates[0]  # type: ignore[return-value]  # CodeEntity has UUID id, EntityLike expects str
        elif len(candidates) > 1:
            return self._disambiguate(candidates, pattern, source_repository_id, relation_type)  # type: ignore[arg-type]  # CodeEntity list vs EntityLike list

        return None

    def _matches_receiver_context(
        self,
        candidate_qualified_name: str,
        receiver_expr: str | None,
    ) -> bool:
        """
        Check if candidate entity matches the receiver context.

        Args:
            candidate_qualified_name: E.g., "myapp.ChartWriter.get"
            receiver_expr: E.g., "chart_writer" or "ctx.redis"

        Returns:
            True if receiver suggests this candidate is likely correct
        """
        if not receiver_expr:
            return True  # No receiver info, can't discriminate

        # Extract potential type name from receiver expression
        # "chart_writer" → "ChartWriter"
        # "ctx.redis" → "Redis"
        # "writer" → "Writer"

        # Simple heuristic: snake_case receiver to PascalCase class
        receiver_parts = receiver_expr.split(".")
        last_part = receiver_parts[-1]  # "redis" from "ctx.redis"

        # Convert snake_case to PascalCase
        type_hint = "".join(word.capitalize() for word in last_part.split("_"))

        # Check if candidate qualified name contains this type
        return type_hint.lower() in candidate_qualified_name.lower()

    def _disambiguate(
        self,
        candidates: list[EntityLike],
        pattern: str,
        source_repository_id: str | UUID | None,
        relation_type: str | None,
    ) -> EntityLike | None:
        """Disambiguate multiple candidates for a reference target."""
        working = list(candidates)

        # Step 1: Same-repository preference
        if source_repository_id:
            # Convert both to string for comparison if needed
            source_id_str = (
                str(source_repository_id)
                if isinstance(source_repository_id, UUID)
                else source_repository_id
            )
            same_repo = [
                c
                for c in working
                if (str(c.repository_id) if isinstance(c.repository_id, UUID) else c.repository_id)
                == source_id_str
            ]
            if len(same_repo) == 1:
                return same_repo[0]
            if same_repo:
                working = same_repo

        # Step 2: Longest suffix match
        dotted = [c for c in working if c.qualified_name.endswith(pattern)]
        if len(dotted) == 1:
            return dotted[0]
        if dotted:
            working = dotted

        # Step 3: Entity type preference
        if relation_type and len(working) > 1:
            preferred = self._preferred_entity_types(relation_type)
            if preferred:
                typed = [c for c in working if c.entity_type.value in preferred]
                if len(typed) == 1:
                    return typed[0]
                if typed:
                    working = typed

        # Step 4: Shortest qualified name (most direct definition)
        working.sort(key=lambda c: len(c.qualified_name))
        logger.debug(
            "Disambiguated reference: pattern={} chosen={} over={}",
            pattern,
            working[0].qualified_name,
            [c.qualified_name for c in working[1:]],
        )
        return working[0]

    @staticmethod
    def _preferred_entity_types(relation_type: str) -> set[str] | None:
        """Return preferred entity types for a given relation type."""
        mapping: dict[str, set[str]] = {
            "extends": {EntityType.CLASS.value, EntityType.INTERFACE.value},
            "implements": {EntityType.INTERFACE.value},
            "calls": {EntityType.FUNCTION.value, EntityType.METHOD.value},
            "imports": {
                EntityType.MODULE.value,
                EntityType.CLASS.value,
                EntityType.FUNCTION.value,
            },
            "instantiates": {EntityType.CLASS.value},
            "uses_type": {
                EntityType.CLASS.value,
                EntityType.TYPE_ALIAS.value,
                EntityType.INTERFACE.value,
            },
        }
        return mapping.get(relation_type)
