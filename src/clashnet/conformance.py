"""Fixture conformance CLI.

Validates every bundled fixture against the schema it names. Consumer repositories should
run the same fixtures against the messages they emit; a fixture change is a contract
change.
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib import resources
from typing import TypedDict

from .validate import errors


class Result(TypedDict):
    fixture: str
    schema: str
    ok: bool
    errors: list[str]


def schema_for(fixture: str) -> str:
    """Map a fixture stem to its schema name."""
    if fixture.startswith("action_"):
        return "action"
    if fixture.startswith("envelope_"):
        return "envelope"
    if fixture == "capabilities":
        return "capabilities"
    if fixture.endswith("_state"):
        return "state"
    raise ValueError(f"no schema mapping for fixture {fixture!r}")


def _fixtures() -> list[tuple[str, str, object]]:
    root = resources.files("clashnet") / "fixtures"
    items = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.name.endswith(".json"):
            continue
        stem = entry.name[: -len(".json")]
        items.append((entry.name, schema_for(stem), json.loads(entry.read_text(encoding="utf-8"))))
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="clashnet-conformance")
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args(argv)

    try:
        results: list[Result] = []
        for name, schema_name, instance in _fixtures():
            found = errors(instance, schema_name)
            results.append(
                Result(fixture=name, schema=schema_name, ok=not found, errors=found)
            )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    failed = [result for result in results if not result["ok"]]
    if args.json:
        print(json.dumps({"ok": not failed, "checked": results}, indent=2))
    else:
        for result in results:
            status = "ok  " if result["ok"] else "FAIL"
            print(f"{status} {result['fixture']} ({result['schema']})")
            for message in result["errors"]:
                print(f"     {message}")
        print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")

    return 0 if not failed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
