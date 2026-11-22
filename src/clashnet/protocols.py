"""Structural Protocols for models and vision backends.

These are ``typing.Protocol`` definitions, not base classes. A model implementation does
not import or inherit anything from this package to satisfy them; it only has to expose
the same shape. This keeps the public contract and implementations independent.
"""

from __future__ import annotations

from typing import Protocol

from .types import Action, State


class Vision(Protocol):
    """Frame -> State."""

    id: str
    version: str

    def analyze(self, frame: bytes, meta: dict[str, object]) -> State:
        """Return the state for one captured frame."""
        ...


class Policy(Protocol):
    """State history -> Action."""

    id: str
    version: str

    def reset(self, session_id: str, deck: list[str] | None = None) -> None:
        """Start a new fight/session."""
        ...

    def observe(self, state: State) -> None:
        """Append one state to the policy's history."""
        ...

    def act(self, state: State, playable: list[int] | None = None) -> Action:
        """Return the next action for the current state."""
        ...
