"""Meeting session state machine.

Tracks the lifecycle of a meeting bot session through well-defined
states with validated transitions. Prevents invalid state changes
and provides a clear audit trail of session progression.

Phase 6 implementation.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.context.manager import ContextManager

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Valid states for a meeting bot session.

    State flow:
        PENDING -> JOINING -> LISTENING -> RESPONDING -> LISTENING -> ... -> ENDED
                                                                     |
        Any state -------------------------------------------------> FAILED
    """

    PENDING = "pending"
    JOINING = "joining"
    LISTENING = "listening"
    RESPONDING = "responding"
    ENDED = "ended"
    FAILED = "failed"


# Valid state transitions: maps current state to allowed next states
VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.PENDING: {SessionState.JOINING, SessionState.FAILED},
    SessionState.JOINING: {SessionState.LISTENING, SessionState.FAILED},
    SessionState.LISTENING: {
        SessionState.RESPONDING,
        SessionState.ENDED,
        SessionState.FAILED,
    },
    SessionState.RESPONDING: {
        SessionState.LISTENING,
        SessionState.ENDED,
        SessionState.FAILED,
    },
    SessionState.ENDED: set(),
    SessionState.FAILED: set(),
}


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not permitted."""


class MeetingSession:
    """State machine for tracking a bot's meeting session lifecycle.

    Enforces valid state transitions and maintains session metadata
    including timestamps for each state change.

    Attributes:
        session_id: Unique identifier for this session.
        meeting_id: Identifier for the meeting this session belongs to.
        state: Current session state.
        context_manager: Context manager instance for transcript and RAG.
        agent_config: Configuration dict for the agent behaviour.
    """

    def __init__(
        self,
        meeting_id: str,
        agent_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a new meeting session in PENDING state.

        Args:
            meeting_id: Identifier for the meeting being joined.
            agent_config: Agent configuration dict with keys such as
                ``system_prompt``, ``mode``, and ``agent_name``.
        """
        self.session_id: str = str(uuid4())
        self.meeting_id: str = meeting_id
        self.agent_config: dict[str, Any] = agent_config or {}
        self.state: SessionState = SessionState.PENDING
        self.context_manager: ContextManager = ContextManager()

        # Bot ID assigned by Recall.ai after deployment
        self.bot_id: str | None = None

        # Timestamps
        now = datetime.now(timezone.utc)
        self.created_at: datetime = now
        self._start_monotonic: float = time.monotonic()

        # Transition history: list of (iso_timestamp, state) tuples
        self._history: list[tuple[str, SessionState]] = [
            (now.isoformat(), SessionState.PENDING),
        ]

        logger.info(
            "Session %s created for meeting %s (state=%s)",
            self.session_id,
            self.meeting_id,
            self.state.value,
        )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def transition(self, new_state: SessionState) -> None:
        """Transition the session to a new state.

        Validates that the transition is allowed before applying it.

        Args:
            new_state: The target state to transition to.

        Raises:
            InvalidTransitionError: If the transition from the current
                state to *new_state* is not permitted.
        """
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self.state.value!r} to "
                f"{new_state.value!r}. Allowed transitions: "
                f"{[s.value for s in allowed]}"
            )

        old_state = self.state
        self.state = new_state
        now_iso = datetime.now(timezone.utc).isoformat()
        self._history.append((now_iso, new_state))

        logger.info(
            "Session %s transitioned %s -> %s",
            self.session_id,
            old_state.value,
            new_state.value,
        )

    def get_state(self) -> str:
        """Return the current session state as a string.

        Returns:
            The current state value (e.g., "listening", "responding").
        """
        return self.state.value

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True if the session is in an active audio-processing state."""
        return self.state in (SessionState.LISTENING, SessionState.RESPONDING)

    def get_duration(self) -> float:
        """Return seconds elapsed since the session was created.

        Uses monotonic time for drift-free measurement.

        Returns:
            Duration in seconds as a float.
        """
        return time.monotonic() - self._start_monotonic

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the session to a dictionary for API responses.

        Returns:
            Dictionary containing all session metadata.
        """
        return {
            "session_id": self.session_id,
            "meeting_id": self.meeting_id,
            "state": self.state.value,
            "bot_id": self.bot_id,
            "agent_config": self.agent_config,
            "created_at": self.created_at.isoformat(),
            "duration_seconds": round(self.get_duration(), 2),
            "is_active": self.is_active,
            "history": [
                {"timestamp": ts, "state": state.value}
                for ts, state in self._history
            ],
        }
