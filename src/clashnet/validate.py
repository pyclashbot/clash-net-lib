"""JSON Schema validation for CNP messages.

The core package has no runtime dependencies. Validation is opt-in via
``clash-net-lib[validate]``; ``jsonschema`` is imported lazily so importing ``clashnet``
stays dependency-free.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

_SCHEMAS = ("envelope", "state", "action", "capabilities")


class ContractError(ValueError):
    """One or more schema or semantic violations."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _read(name: str) -> dict[str, Any]:
    path = resources.files("clashnet") / "schema" / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=len(_SCHEMAS))
def schema(name: str) -> dict[str, Any]:
    if name not in _SCHEMAS:
        raise KeyError(f"unknown schema {name!r}; expected one of {_SCHEMAS}")
    return _read(name)


@lru_cache(maxsize=1)
def _registry() -> Any:
    try:
        from referencing import Registry, Resource
    except ImportError as exc:  # pragma: no cover - exercised by missing extra
        raise RuntimeError("install 'clash-net-lib[validate]' to validate messages") from exc

    entries = []
    for name in _SCHEMAS:
        data = schema(name)
        entries.append((data["$id"], Resource.from_contents(data)))
    return Registry().with_resources(entries)


def errors(instance: Any, schema_name: str) -> list[str]:
    """Return human-readable violations for ``instance`` against one schema."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - exercised by missing extra
        raise RuntimeError("install 'clash-net-lib[validate]' to validate messages") from exc

    validator = jsonschema.Draft202012Validator(schema(schema_name), registry=_registry())
    found = []
    for error in validator.iter_errors(instance):
        path = "/".join(str(part) for part in error.absolute_path) or "<root>"
        found.append(f"{path}: {error.message}")
    return found


def validate(instance: Any, schema_name: str) -> None:
    found = errors(instance, schema_name)
    if found:
        raise ContractError(found)


def validate_state(state: Any) -> None:
    validate(state, "state")
    cards = state.get("hand_cards", []) if isinstance(state, dict) else []
    slots = [card.get("slot") for card in cards if isinstance(card, dict)]
    if len(slots) != len(set(slots)):
        raise ContractError(["hand_cards: slots must be unique"])


def validate_action(action: Any) -> None:
    validate(action, "action")


def validate_envelope(message: Any) -> None:
    validate(message, "envelope")


def validate_capabilities(capabilities: Any) -> None:
    validate(capabilities, "capabilities")
