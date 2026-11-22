# clash-net-lib

The public shape contract for the **Clash Net Protocol (CNP)**.

This repository defines the messages and domain types that a local bot, a remote
server, and a third-party model can all speak. It is a **shape library**, not an
inference runtime: no transport, no models, no auth, no game logic.

- Normative contract: [CONTRACT.md](CONTRACT.md)
- Protocol name: **Clash Net Protocol (CNP)**
- Version: `0.1.0`
- State schema: `1.1`
- License: MIT

## Status

`0.1.0` is the first shape-only release. It contains JSON Schema, Python types,
`Vision`/`Policy` Protocols, a fixture vocabulary, and a conformance CLI. Bindings and
adapters land in consumer repositories (`py-clash-bot` and others).

## Install

`0.1.0` is not on PyPI yet. From this repository:

```bash
uv sync --extra test
uv run clashnet-conformance
```

When published:

```bash
pip install clash-net-lib             # types + Protocols only
pip install 'clash-net-lib[validate]' # + JSON Schema validation
```

Python 3.12+.

## Use

```python
from clashnet import State, Action, Vision, Policy
from clashnet.validate import validate_state, validate_action

validate_state(state)
validate_action(action)
```

Conformance over the bundled fixtures:

```bash
clashnet-conformance
clashnet-conformance --json
```

## Layout

```
CONTRACT.md                  normative contract
src/clashnet/types.py        TypedDicts for messages, state, action
src/clashnet/protocols.py    Vision and Policy Protocols
src/clashnet/vocab.py        fixture vocabulary + stable hash
src/clashnet/schema/         JSON Schema (source of truth)
src/clashnet/fixtures/       golden / degenerate / action / envelope fixtures
src/clashnet/validate.py     lazy jsonschema validation
src/clashnet/conformance.py  fixture conformance CLI
tests/                       schema + fixture + conformance tests
```

## Compatibility

- Required core: `v`, `type`, `seq` (plus `session_id` for stateful messages).
- Everything else is optional and may be `null`/`unknown`.
- Unknown fields are ignored; unknown cards and unit classes pass through as strings.
- Additive changes within a minor; breaking changes bump the major.
- Servers fill defaults; clients must tolerate missing optional fields.

## License

MIT. See [LICENSE](LICENSE).
