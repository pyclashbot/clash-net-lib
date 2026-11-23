# Clash Net Protocol (CNP) — v0.1

Status: **draft for the first shape-only release.** `0.1.0` defines the envelope, state,
action, capability handshake, adapter Protocols, and conformance fixtures. It does not
define a transport, auth, or any model.

This document is normative for `clash-net-lib` `0.1.x` and `0.2.x` and state schema `1.1`.

## 1. Scope

CNP is the public shape shared by:

- a local bot (`py-clash-bot`) that captures frames and executes actions;
- a remote server that produces state and plays;
- any third-party model that wants to plug in behind a `Policy` or `Vision` adapter.

The contract is **model-agnostic**. A model's featurizer, weights, thresholds, and
business logic stay behind its adapter. Only `State` and `Action` cross a repo or network
boundary.

Not in scope for the core shape: transport bindings, authentication, rate limits,
retention enforcement, model loading, training data formats. `0.2.0` adds one optional
reference binding (`clashnet.client`); the core stays transport-free.

## 2. Terms

- **Frame** — one captured image plus capture metadata.
- **State** — the vision result for a frame: units, hand, elixir, timer, towers, summary,
  derived signals.
- **Action** — a decision: deploy a card at a location, trigger an ability, or explicitly
  do nothing.
- **Capabilities** — what a server can do, returned by `hello_ack`.
- **Playable slots** — hand slots that are ground-truth deployable for a frame.

## 3. Versioning

- `v` is the protocol version (`"0.1"`).
- `schema_version` is the state schema version (`"1.1"`).
- `CONTRACT_VERSION` (`0.1.0`) is the package/spec version.
- Additive fields and enum values may appear in a minor release. Clients MUST ignore
  unknown fields and unknown enum values they do not understand.
- Removals, renames, and semantic changes bump the major.
- Servers SHOULD advertise `state_schema` and `actions` in `hello_ack`; clients SHOULD
  use that instead of assuming.

## 4. Envelope

### 4.1 Client messages

```jsonc
{
  "v": "0.1",
  "type": "hello",
  "session_id": "01J...",
  "client": { "name": "py-clash-bot", "version": "0.0.0" }
}
```

```jsonc
{
  "v": "0.1",
  "type": "frame",
  "session_id": "01J...",
  "seq": 42,
  "frame_ts": 1766000000000,
  "fight_id": "optional",
  "image": { "b64": "...", "format": "jpeg", "w": 419, "h": 633 },
  "want": ["state", "play"],
  "consent": { "training": true }
}
```

```jsonc
{ "v": "0.1", "type": "bye", "session_id": "01J..." }
```

- `session_id` is stable per bot session or fight.
- `seq` is monotonic per session. A gap means dropped frames, not a reset.
- `frame_ts` is the client clock in Unix milliseconds.
- `image.b64` is for JSON bindings. Binary bindings carry the image out of band and MAY
  omit `b64`; `format`, `w`, and `h` are still declared.
- `consent.training` is optional in the shape. See §5.

### 4.2 Server messages

```jsonc
{
  "v": "0.1",
  "type": "hello_ack",
  "capabilities": {
    "vision": true,
    "play": true,
    "actions": ["deploy", "none", "ability"],
    "state_schema": "1.1",
    "frame": { "formats": ["jpeg", "webp", "png"], "max_bytes": 32768 },
    "max_hz": 3,
    "models": [{ "id": "policy", "version": "2026-07", "featurizer": "fixture-1" }],
    "retention": { "requires_consent": true }
  }
}
```

```jsonc
{ "v": "0.1", "type": "state", "seq": 42, "state": { /* §6 */ } }
```

```jsonc
{
  "v": "0.1",
  "type": "play",
  "seq": 42,
  "play": { /* §7 */ },
  "playable": [0, 1, 3],
  "model": { "id": "policy", "version": "2026-07" },
  "timings": { "server_ms": 410 }
}
```

```jsonc
{ "v": "0.1", "type": "error", "seq": 42, "error": { "code": "bad_image", "message": "..." } }
```

`play` may be `null` when the server has no play for that frame. `playable` is
authoritative for deployability; clients SHOULD still re-check before clicking.

### 4.3 Reference WebSocket binding (`0.2.0`)

`clash-net-lib[client]` ships `clashnet.client.Client`:

- WebSocket; one JSON text message per frame; images are base64.
- `hello` -> `hello_ack` is required before frames; the response carries capabilities.
- Text messages larger than 30 KB are fragmented.
- Responses correlate by `seq`; clients drop stale plays.
- Reconnect with backoff and a fresh `hello`.
- `consent.training` is sent on every frame when configured.
- `send_frame()` is non-blocking; `poll()` / `drain()` receive; `request()` / `infer()` /
  `decide()` are blocking conveniences.
- The core package never imports `websockets`; it is only in the `[client]` extra.

## 5. Consent and retention

`consent.training` is a boolean on `frame` messages. The library only defines the field;
enforcement lives in the server.

Server policy for `0.1.0`:

- A server MAY require an explicit `consent` object on frames.
- `training: true` permits retention for the training flywheel.
- `training: false` means do not retain the frame.
- Servers that require consent reject frames without it.
- Local bindings and local models may omit `consent` entirely.

Servers advertise this with `capabilities.retention.requires_consent`.

## 6. State

State schema `1.1`. Required skeleton: `schema_version`, `in_fight`, `image_size`,
`units`, `hand_cards`, `towers`. Everything else is optional.

```jsonc
{
  "schema_version": "1.1",
  "in_fight": true,
  "image_size": [419, 633],
  "arena": { "rect_px": [52, 57, 367, 476] },
  "units": [
    {
      "bbox": [136, 397, 182, 448],
      "center": [159, 422],
      "center_norm": [0.34, 0.87],
      "cell": 87,
      "class": "Skeleton King",
      "class_conf": 0.53,
      "side": "friendly",
      "side_conf": 0.99,
      "detection_conf": 0.48
    }
  ],
  "hand_cards": [
    { "slot": 0, "card": "Snowball", "conf": 0.45, "empty": false, "affordable": true }
  ],
  "elixir": 6.5,
  "timer": {
    "seconds_remaining": 161,
    "mmss": "2:41",
    "overtime": false,
    "phase": "regular"
  },
  "towers": {
    "enemy_left":     { "status": "destroyed", "health_percent": 0.0,  "conf": 0.98, "alive": false },
    "enemy_right":    { "status": "middle",    "health_percent": 62.5, "conf": 0.91, "alive": true  },
    "enemy_main":     { "status": "full",      "health_percent": 100.0,"conf": 0.97, "alive": true  },
    "friendly_left":  { "status": "full",      "health_percent": 100.0,"conf": 0.99, "alive": true  },
    "friendly_right": { "status": "full",      "health_percent": 100.0,"conf": 0.99, "alive": true  },
    "friendly_main":  { "status": "full",      "health_percent": 100.0,"conf": 0.99, "alive": true  }
  },
  "summary": { "unit_count": 1, "friendly_units": 1, "enemy_units": 0 },
  "derived": { "advantage": 0.12, "terminal": false, "winner": null },
  "vocab": { "version": "fixtures-0.1", "hash": "85bc65aa96323350" },
  "timings": { "total_ms": 120.0 }
}
```

Rules:

- **Hand slots are 0-3.** State `slot` and action `slot` use the same index.
- `elixir` is a float or `null`, range 0-10.
- `units` and `hand_cards` may be empty. `hand_cards` has at most four entries, unique
  slots.
- `towers` always has the six named keys. Missing observation is `status: "unknown"`.
- `class` and `card` are strings. Unknown values pass through; clients must not fail.
- `center_norm`, `cell`, `summary`, `derived`, `vocab`, and `timings` are optional
  conveniences. `derived.advantage` is public shape; the formula behind it stays in the
  model.
- Coordinates: `bbox`/`center` are pixels in the declared `image_size`. `center_norm` is
  over `arena.rect_px` when present, else the full image.

## 7. Action

```jsonc
{ "type": "deploy", "slot": 2, "card": "Hog Rider",
  "xy_px": [212, 410], "xy_norm": [0.51, 0.59], "cell": 87,
  "game_s": 118.4, "source": "remote-policy",
  "model": { "id": "policy", "version": "2026-07" }, "confidence": 0.42 }
```

```jsonc
{ "type": "none", "game_s": 119.0, "source": "remote-policy" }
```

```jsonc
{ "type": "ability", "card": "Skeleton King", "xy_norm": [0.5, 0.5],
  "game_s": 120.0, "source": "local-heuristic" }
```

Rules:

- `type` is `deploy`, `none`, or `ability`.
- `none` is an explicit decision, not an absent reply. It carries no `slot` or
  coordinates.
- `deploy` requires `slot` and `xy_norm`; `xy_px` and `cell` are optional.
- `ability` may carry `card` and a coordinate; otherwise it is a button press.
- `game_s` is the fight clock at the decision. `source` records provenance
  (`local-heuristic`, `remote-policy`, `hf-policy`, `human`, ...).
- `playable` (envelope) is authoritative for which slots can deploy.

## 8. Adapter Protocols

```python
class Vision(Protocol):
    id: str
    version: str
    def analyze(self, frame: bytes, meta: dict) -> State: ...

class Policy(Protocol):
    id: str
    version: str
    def reset(self, session_id: str, deck: list[str] | None = None) -> None: ...
    def observe(self, state: State) -> None: ...
    def act(self, state: State, playable: list[int] | None = None) -> Action: ...
```

Model-specific featurizers live behind `Policy`. A model plugs in by mapping `State` to
its own features and mapping its output to an `Action`; no fork of the model belongs in
the bot.

## 9. Defaulting and failure behavior

| Situation | Behavior |
| --- | --- |
| Elixir unreadable | `elixir: null`; `affordable` omitted or `null` |
| No card detected | `card: "unknown"`, `empty: true` |
| Unknown unit class | `class` is the raw string; confidence may be low |
| Frame mid-boot | `in_fight: false`, empty arrays, six unknown towers, null timer |
| Dropped frame | `seq` gap; server treats it as a loss, not a reset |
| Old client, new server | Unknown fields ignored; capabilities set expectations |
| Old server, new client | Client tolerates missing optional fields |
| No play | `play: null`, or `type: "none"`; both are valid |

## 10. Conformance

`clashnet-conformance` validates the bundled fixtures against the JSON Schemas in
`src/clashnet/schema/`. Consumer repositories SHOULD run the same fixtures against the
messages they emit. A fixture change is a contract change.

The suite covers:

- golden state, degenerate state;
- deploy, none, and ability actions;
- frame and hello envelopes;
- capabilities with retention;
- invalid slot, missing `seq`, and unknown-field tolerance.

## 11. Changes from 0.0.x

`0.0.x` was a two-file sketch: `DecisionInput`/`Decision`/`DecisionMaker` with a numpy
array input and a pixel-only `FightDecisionValue`. It is superseded. This release:

- replaces `clashnetlib` with `clashnet`;
- drops the numpy dependency and ABC inheritance;
- adds JSON Schema, versioning, `seq`, state, capabilities, consent, and conformance;
- normalizes hand slots to 0-3 and coordinates to `xy_norm` + `xy_px`.

## 12. Post-0.1 items

Not in this release; each is additive or a separate binding:

- additional transport bindings (binary WebSocket, AWS API Gateway);
- auth and key minting;
- full card/unit vocabulary artifact (fixture-only baseline today);
- retention enforcement and deletion;
- model registry;
- replay/offline batch profile;
- importer from `pcb-pack/v1` recordings.
