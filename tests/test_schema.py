from __future__ import annotations

import json
from importlib import resources

import pytest

from clashnet.validate import (
    ContractError,
    validate_action,
    validate_capabilities,
    validate_envelope,
    validate_state,
)
from clashnet.version import STATE_SCHEMA_VERSION


def fixture(name: str):
    path = resources.files("clashnet") / "fixtures" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["golden_state", "degenerate_state"])
def test_states_validate(name: str) -> None:
    validate_state(fixture(name))


@pytest.mark.parametrize("name", ["action_deploy", "action_none", "action_ability"])
def test_actions_validate(name: str) -> None:
    validate_action(fixture(name))


@pytest.mark.parametrize("name", ["envelope_frame", "envelope_hello"])
def test_envelopes_validate(name: str) -> None:
    validate_envelope(fixture(name))


def test_capabilities_validate() -> None:
    validate_capabilities(fixture("capabilities"))


def test_unknown_card_unit_and_field_are_tolerated() -> None:
    state = fixture("golden_state")
    state["hand_cards"][0]["card"] = "Card From 2027"
    state["units"][0]["class"] = "Unit From 2027"
    state["future_field"] = {"anything": True}
    validate_state(state)


def test_deploy_requires_slot_and_norm() -> None:
    action = fixture("action_deploy")
    del action["slot"]
    with pytest.raises(ContractError):
        validate_action(action)

    action = fixture("action_deploy")
    del action["xy_norm"]
    with pytest.raises(ContractError):
        validate_action(action)


def test_slot_out_of_range_is_rejected() -> None:
    action = fixture("action_deploy")
    action["slot"] = 4
    with pytest.raises(ContractError):
        validate_action(action)


def test_none_forbids_slot_and_coordinates() -> None:
    action = fixture("action_none")
    action["slot"] = 1
    with pytest.raises(ContractError):
        validate_action(action)


def test_frame_requires_seq() -> None:
    frame = fixture("envelope_frame")
    del frame["seq"]
    with pytest.raises(ContractError):
        validate_envelope(frame)


def test_state_message_cross_reference() -> None:
    validate_envelope({"v": "0.1", "type": "state", "seq": 1, "state": fixture("golden_state")})


def test_play_message_cross_reference_and_null_play() -> None:
    validate_envelope(
        {
            "v": "0.1",
            "type": "play",
            "seq": 1,
            "play": fixture("action_deploy"),
            "playable": [2],
        }
    )
    validate_envelope({"v": "0.1", "type": "play", "seq": 2, "play": None})


def test_hand_slots_must_be_unique() -> None:
    state = fixture("golden_state")
    state["hand_cards"][1]["slot"] = 0
    with pytest.raises(ContractError):
        validate_state(state)


def test_vocab_hash_matches_fixture() -> None:
    from clashnet import VOCAB_HASH, vocab_ref

    assert VOCAB_HASH == "85bc65aa96323350"
    assert vocab_ref() == {"version": "fixtures-0.1", "hash": VOCAB_HASH}
    assert fixture("golden_state")["vocab"] == vocab_ref()


def test_schema_versions_match_fixtures() -> None:
    assert fixture("golden_state")["schema_version"] == STATE_SCHEMA_VERSION
    assert fixture("degenerate_state")["schema_version"] == STATE_SCHEMA_VERSION
    assert fixture("capabilities")["state_schema"] == STATE_SCHEMA_VERSION


def test_arena_norm_and_px_agree_within_one_pixel() -> None:
    state = fixture("golden_state")
    x0, y0, x1, y1 = state["arena"]["rect_px"]
    assert (x0, y0, x1, y1) == (50, 57, 367, 477)

    for unit in state["units"]:
        nx, ny = unit["center_norm"]
        px, py = unit["center"]
        assert abs(round(x0 + nx * (x1 - x0)) - px) <= 1
        assert abs(round(y0 + ny * (y1 - y0)) - py) <= 1

    action = fixture("action_deploy")
    nx, ny = action["xy_norm"]
    px, py = action["xy_px"]
    assert abs(round(x0 + nx * (x1 - x0)) - px) <= 1
    assert abs(round(y0 + ny * (y1 - y0)) - py) <= 1
