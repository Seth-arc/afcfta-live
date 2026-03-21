"""Reduce current status assertions and active transitions into an overlay."""

from __future__ import annotations

from app.repositories.status_repository import StatusRepository
from app.schemas.status import ActiveTransitionOverlay, StatusOverlay


class StatusService:
    """Service for entity-level status overlays and transition warnings."""

    def __init__(self, status_repository: StatusRepository) -> None:
        self.status_repository = status_repository

    async def get_status_overlay(self, entity_type: str, entity_key: str) -> StatusOverlay:
        """Fetch current status plus active transitions and derive confidence/constraints."""

        status = await self.status_repository.get_status(entity_type, entity_key)
        transitions = await self.status_repository.get_active_transitions(entity_type, entity_key)

        active_transitions = [
            ActiveTransitionOverlay(
                transition_type=transition["transition_type"],
                description=transition["transition_text_verbatim"],
                start_date=transition["start_date"],
                end_date=transition["end_date"],
                review_trigger=transition["review_trigger"],
            )
            for transition in transitions
        ]

        if status is None:
            return StatusOverlay(
                status_type="unknown",
                confidence_class="incomplete",
                active_transitions=active_transitions,
                constraints=[transition.description for transition in active_transitions],
                source_text_verbatim=None,
            )

        status_type = status["status_type"]
        constraints = self._build_constraints(status_type, active_transitions)
        return StatusOverlay(
            status_type=status_type,
            effective_from=status["effective_from"],
            effective_to=status["effective_to"],
            confidence_class=self._compute_confidence_class(status_type),
            active_transitions=active_transitions,
            constraints=constraints,
            source_text_verbatim=status["status_text_verbatim"],
        )

    @staticmethod
    def _compute_confidence_class(status_type: str) -> str:
        """Map the resolved status into the API-facing confidence class."""

        if status_type in {"agreed", "in_force"}:
            return "complete"
        if status_type in {"provisional", "pending"}:
            return "provisional"
        return "incomplete"

    def _build_constraints(
        self,
        status_type: str,
        active_transitions: list[ActiveTransitionOverlay],
    ) -> list[str]:
        """Derive warning strings from the current status and transition clauses."""

        constraints: list[str] = []
        if status_type == "pending":
            constraints.append("Rule is pending — not yet enforceable")
        if status_type == "provisional":
            constraints.append("Rule is provisional — subject to change")

        for transition in active_transitions:
            constraints.append(transition.description)
        return constraints
