from __future__ import annotations

from clashnet import Action, State, Unit
from clashnet.version import CONTRACT_VERSION, PROTOCOL_VERSION, STATE_SCHEMA_VERSION


def test_version_constants() -> None:
    assert CONTRACT_VERSION == "0.2.0"
    assert PROTOCOL_VERSION == "0.1"
    assert STATE_SCHEMA_VERSION == "1.1"


def test_state_required_keys() -> None:
    assert State.__required_keys__ == frozenset(
        {"schema_version", "in_fight", "image_size", "units", "hand_cards", "towers"}
    )


def test_unit_required_keys_and_keyword_field() -> None:
    assert Unit.__required_keys__ == frozenset({"bbox", "class", "side"})
    assert "class" in Unit.__annotations__


def test_action_is_importable() -> None:
    assert Action is not None
