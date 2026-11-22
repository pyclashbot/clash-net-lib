from __future__ import annotations

import pytest

from clashnet.conformance import main, schema_for


def test_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "0 failed" in output


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json"]) == 0
    output = capsys.readouterr().out
    assert '"ok": true' in output


@pytest.mark.parametrize(
    ("fixture", "schema"),
    [
        ("golden_state", "state"),
        ("degenerate_state", "state"),
        ("action_deploy", "action"),
        ("action_none", "action"),
        ("action_ability", "action"),
        ("envelope_frame", "envelope"),
        ("envelope_hello", "envelope"),
        ("capabilities", "capabilities"),
    ],
)
def test_fixture_schema_mapping(fixture: str, schema: str) -> None:
    assert schema_for(fixture) == schema


def test_unknown_fixture_raises() -> None:
    with pytest.raises(ValueError):
        schema_for("mystery")
