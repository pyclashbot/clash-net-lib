# clash-net-lib

The public shape contract for the **Clash Net Protocol (CNP)**.

This repository defines the messages and domain types that a local bot, a remote
server, and a third-party model can all speak. It is a **shape library**, not an
inference runtime: no transport, no models, no auth, no game logic.

- Normative contract: [CONTRACT.md](CONTRACT.md)
- Protocol name: **Clash Net Protocol (CNP)**
- Version: `0.2.0`
- State schema: `1.2`
- License: MIT

## Status

`0.2.0` adds the optional reference WebSocket client (`clashnet.client`). The core is
still shape-only: JSON Schema, Python types, `Vision`/`Policy` Protocols, a fixture
vocabulary, and a conformance CLI. Consumer adapters live in consumer repositories.

## Install

`0.2.0` is not on PyPI yet. From this repository:

```bash
uv sync --extra test
uv run clashnet-conformance
```

When published:

```bash
pip install clash-net-lib             # types + Protocols only
pip install 'clash-net-lib[validate]' # + JSON Schema validation
pip install 'clash-net-lib[client]'   # + reference WebSocket client
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

## Client

The reference client is a thin synchronous WebSocket binding: `hello`/`hello_ack`,
framing, base64, 30 KB fragmentation, `seq` correlation, and reconnect. It contains no
capture, game logic, or model code.

```python
from clashnet.client import Client

with Client("wss://example/ws", consent_training=False) as client:
    play = client.decide(jpeg_bytes, w=419, h=633)
    action = play["play"]

# streaming (non-blocking send + poll)
client = Client("wss://example/ws", consent_training=False)
client.connect()
client.send_frame(jpeg_bytes, w=419, h=633, seq=1, want=("state", "play"))
message = client.poll(timeout=0.5)
client.close()

# one-shot helpers
from clashnet.client import decide, infer

play = decide("wss://example/ws", jpeg_bytes, w=419, h=633, consent_training=False)
state = infer("wss://example/ws", jpeg_bytes, w=419, h=633)
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
src/clashnet/client.py       optional reference WebSocket client
tests/                       schema + fixture + client tests
```

## Compatibility

- Required core: `v`, `type`, `seq` (plus `session_id` for stateful messages).
- Everything else is optional and may be `null`/`unknown`.
- Unknown fields are ignored; unknown cards and unit classes pass through as strings.
- Additive changes within a minor; breaking changes bump the major.
- Servers fill defaults; clients must tolerate missing optional fields.

## License

MIT. See [LICENSE](LICENSE).
