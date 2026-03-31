"""Reduce current status assertions and active transitions into overlays."""

from __future__ import annotations

from datetime import date

from app.repositories.status_repository import StatusRepository
from app.schemas.status import ActiveTransitionOverlay, StatusOverlay


class StatusService:
    """Service for entity-level status overlays and transition warnings."""

    def __init__(self, status_repository: StatusRepository) -> None:
        self.status_repository = status_repository

    async def get_status_overlay(
        self,
        entity_type: str,
        entity_key: str,
        as_of_date: date | None = None,
    ) -> StatusOverlay:
        """Fetch one status overlay active on the requested date."""

        overlays = await self.get_status_overlays([(entity_type, entity_key)], as_of_date)
        return overlays[(entity_type, entity_key)]

    async def get_status_overlays(
        self,
        targets: list[tuple[str, str]],
        as_of_date: date | None = None,
    ) -> dict[tuple[str, str], StatusOverlay]:
        """Fetch multiple overlays in one repository round trip."""

        rows = await self.status_repository.get_status_overlay_rows(targets, as_of_date)
        overlays: dict[tuple[str, str], StatusOverlay] = {}
        for row in rows:
            entity_type = str(row["entity_type"])
            entity_key = str(row["entity_key"])
            overlays[(entity_type, entity_key)] = self._build_overlay(
                status=row.get("status"),
                transitions=row.get("transitions") or [],
            )

        for entity_type, entity_key in targets:
            overlays.setdefault(
                (entity_type, entity_key),
                self._build_overlay(status=None, transitions=[]),
            )
        return overlays

    def _build_overlay(
        self,
        *,
        status: object,
        transitions: list[object],
    ) -> StatusOverlay:
        """Transform repository payloads into one API-facing overlay."""

        active_transitions = [
            ActiveTransitionOverlay(
                transition_type=str(transition["transition_type"]),
                description=str(transition["transition_text_verbatim"]),
                start_date=transition.get("start_date"),
                end_date=transition.get("end_date"),
                review_trigger=transition.get("review_trigger"),
            )
            for transition in transitions
            if isinstance(transition, dict)
        ]

        if not isinstance(status, dict):
            return StatusOverlay(
                status_type="unknown",
                confidence_class="incomplete",
                active_transitions=active_transitions,
                constraints=[transition.description for transition in active_transitions],
                source_text_verbatim=None,
            )

        status_type = str(status["status_type"])
        constraints = self._build_constraints(status_type, active_transitions)
        return StatusOverlay(
            status_type=status_type,
            effective_from=status.get("effective_from"),
            effective_to=status.get("effective_to"),
            confidence_class=self._compute_confidence_class(status_type),
            active_transitions=active_transitions,
            constraints=constraints,
            source_text_verbatim=status.get("status_text_verbatim"),
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
