"""
SSE Progress Manager.

Thread-safe state for bridging a CPU-bound simulation thread to an
async SSE (Server-Sent Events) generator. Uses a polling approach:
the SSE endpoint polls get_state() every 0.5 seconds rather than
using asyncio.Event across threads.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass


@dataclass
class ProgressState:
    """Current progress state for a simulation session."""
    phase: str = "idle"  # idle | initializing | simulation | rendering | complete | error
    current: int = 0
    total: int = 0
    message: str = ""
    started_at: float = 0.0
    error: str | None = None


class ProgressManager:
    """
    Manages progress state for multiple concurrent simulation sessions.

    Thread-safe: update() is called from background simulation threads,
    while get_state() is called from the async FastAPI event loop.
    ProgressState fields are simple scalars, so reads/writes are atomic
    on CPython (GIL protects against torn reads).
    """

    def __init__(self):
        self._sessions: dict[str, ProgressState] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Store reference to the asyncio event loop (called at startup)."""
        self._loop = loop

    def create_session(self, session_id: str | None = None) -> str:
        """
        Create a new progress tracking session.

        Args:
            session_id: Optional external ID. If None, generates a UUID.

        Returns:
            session_id: UUID string identifying this session.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        self._sessions[session_id] = ProgressState(started_at=time.time())
        return session_id

    def update(self, session_id: str, phase: str, current: int, total: int,
               message: str = ""):
        """
        Update progress state for a session.

        Called from background thread -- updates state that will be read
        by the SSE polling loop.

        Args:
            session_id: Session to update.
            phase: Current phase (initializing, simulation, rendering, complete, error).
            current: Current step number.
            total: Total steps expected.
            message: Human-readable status message.
        """
        state = self._sessions.get(session_id)
        if state:
            state.phase = phase
            state.current = current
            state.total = total
            state.message = message

    def set_error(self, session_id: str, error: str):
        """
        Mark a session as failed with an error message.

        Args:
            session_id: Session to mark.
            error: Error description string.
        """
        state = self._sessions.get(session_id)
        if state:
            state.phase = "error"
            state.error = error
            state.message = f"Error: {error}"

    def get_state(self, session_id: str) -> ProgressState | None:
        """
        Get current progress state for a session.

        Called from the async SSE endpoint (polling every 0.5s).

        Returns:
            ProgressState or None if session not found.
        """
        return self._sessions.get(session_id)

    def get_eta_seconds(self, session_id: str) -> int:
        """
        Estimate remaining time in seconds based on progress so far.

        Returns:
            Estimated seconds remaining, or 0 if unknown.
        """
        state = self._sessions.get(session_id)
        if not state or state.current <= 0 or state.total <= 0:
            return 0

        elapsed = time.time() - state.started_at
        if elapsed <= 0:
            return 0

        rate = state.current / elapsed  # steps per second
        remaining_steps = state.total - state.current
        if rate <= 0:
            return 0

        return max(0, int(remaining_steps / rate))

    def cleanup(self, session_id: str):
        """
        Remove a session's progress state.

        Should be called after the client has received the final result
        or after a timeout.
        """
        self._sessions.pop(session_id, None)

    @property
    def active_sessions(self) -> int:
        """Number of currently tracked sessions."""
        return len(self._sessions)
