"""Meeting session state machine.

Tracks the lifecycle of a meeting bot session through well-defined
states with validated transitions. Prevents invalid state changes
and provides a clear audit trail of session progression.

Phase 2 implementation.
"""

from __future__ import annotations

from enum import Enum


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


class MeetingSession:
    """State machine for tracking a bot's meeting session lifecycle.

    Enforces valid state transitions and maintains session metadata
    including timestamps for each state change.

    Attributes:
        session_id: Unique identifier for this session.
        state: Current session state.
    """

    def __init__(self, session_id: str) -> None:
        """Initialize a new meeting session in PENDING state.

        Args:
            session_id: Unique identifier for this session.
        """
        self.session_id = session_id
        self.state = SessionState.PENDING
        self._history: list[tuple[str, SessionState]] = []
        # TODO: Record initial state with timestamp in history
        raise NotImplementedError("Phase 2 implementation")

    def transition(self, new_state: SessionState) -> None:
        """Transition the session to a new state.

        Validates that the transition is allowed before applying it.

        Args:
            new_state: The target state to transition to.

        Raises:
            ValueError: If the transition from the current state to
                new_state is not permitted.
        """
        # TODO: Validate transition against VALID_TRANSITIONS
        # TODO: Update state and record in history with timestamp
        raise NotImplementedError("Phase 2 implementation")

    def get_state(self) -> str:
        """Return the current session state as a string.

        Returns:
            The current state value (e.g., "listening", "responding").
        """
        # TODO: Return self.state.value
        raise NotImplementedError("Phase 2 implementation")
