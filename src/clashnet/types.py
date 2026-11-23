"""Typed shapes for the Clash Net Protocol.

These are wire shapes, not runtime models. Unknown fields are allowed by design; clients
must ignore fields they do not understand. See ``CONTRACT.md`` for the normative rules.
"""

from typing import Literal, NotRequired, TypedDict

Side = Literal["friendly", "enemy", "unknown"]
TowerStatus = Literal["destroyed", "middle", "full", "unknown"]
TimerPhase = Literal["regular", "overtime", "sudden_death", "unknown"]
ActionType = Literal["deploy", "none", "ability"]
Winner = Literal["friendly", "enemy", "draw"]
ImageFormat = Literal["jpeg", "webp", "png"]


class Arena(TypedDict):
    """Pixel rectangle [x0, y0, x1, y1] in the state image (419x633 for the bot).

    ``center_norm``/``xy_norm`` normalize over this rect; ``xy_px`` stays absolute
    in ``image_size``. Converting between them lands within 1 px; clients clamp
    before clicking.
    """

    rect_px: tuple[int, int, int, int]


# ``class`` is a Python keyword, so Unit uses the functional TypedDict form.
Unit = TypedDict(
    "Unit",
    {
        "bbox": tuple[int, int, int, int],
        "center": NotRequired[tuple[int, int]],
        "center_norm": NotRequired[tuple[float, float]],
        "cell": NotRequired[int],
        "class": str,
        "class_conf": NotRequired[float],
        "side": Side,
        "side_conf": NotRequired[float],
        "detection_conf": NotRequired[float],
    },
)


class HandCard(TypedDict):
    slot: int
    card: str
    conf: NotRequired[float]
    empty: NotRequired[bool]
    affordable: NotRequired[bool | None]


class Timer(TypedDict):
    seconds_remaining: int | None
    mmss: NotRequired[str | None]
    overtime: bool
    phase: TimerPhase


class Tower(TypedDict):
    status: TowerStatus
    health_percent: NotRequired[float | None]
    conf: NotRequired[float | None]
    alive: NotRequired[bool | None]


class Towers(TypedDict):
    enemy_left: Tower
    enemy_right: Tower
    enemy_main: Tower
    friendly_left: Tower
    friendly_right: Tower
    friendly_main: Tower


class Summary(TypedDict, total=False):
    unit_count: int
    friendly_units: int
    enemy_units: int
    raw_detections: int
    tower_filtered: int


class Derived(TypedDict, total=False):
    advantage: float | None
    terminal: bool | None
    winner: Winner | None


class VocabRef(TypedDict):
    version: str
    hash: str


class State(TypedDict):
    schema_version: str
    in_fight: bool
    image_size: tuple[int, int]
    arena: NotRequired[Arena]
    units: list[Unit]
    hand_cards: list[HandCard]
    elixir: NotRequired[float | None]
    timer: NotRequired[Timer | None]
    towers: Towers
    summary: NotRequired[Summary]
    derived: NotRequired[Derived]
    vocab: NotRequired[VocabRef]
    timings: NotRequired[dict[str, object]]


class ModelRef(TypedDict):
    id: str
    version: str
    featurizer: NotRequired[str]


class DeployAction(TypedDict):
    type: Literal["deploy"]
    slot: int
    xy_norm: tuple[float, float]
    card: NotRequired[str | None]
    xy_px: NotRequired[tuple[int, int]]
    cell: NotRequired[int]
    game_s: float
    source: str
    model: NotRequired[ModelRef]
    confidence: NotRequired[float]


class NoneAction(TypedDict):
    type: Literal["none"]
    game_s: float
    source: str
    model: NotRequired[ModelRef]
    confidence: NotRequired[float]


class AbilityAction(TypedDict):
    type: Literal["ability"]
    card: NotRequired[str | None]
    slot: NotRequired[int]
    xy_px: NotRequired[tuple[int, int]]
    xy_norm: NotRequired[tuple[float, float]]
    cell: NotRequired[int]
    game_s: float
    source: str
    model: NotRequired[ModelRef]
    confidence: NotRequired[float]


Action = DeployAction | NoneAction | AbilityAction


class Image(TypedDict):
    format: ImageFormat
    w: int
    h: int
    b64: NotRequired[str]


class Consent(TypedDict):
    training: bool


class ClientInfo(TypedDict, total=False):
    name: str
    version: str


class FrameMessage(TypedDict):
    v: Literal["0.1"]
    type: Literal["frame"]
    session_id: str
    seq: int
    frame_ts: NotRequired[int]
    fight_id: NotRequired[str | None]
    image: NotRequired[Image]
    want: NotRequired[list[Literal["state", "play"]]]
    consent: NotRequired[Consent]
    client: NotRequired[ClientInfo]


class HelloMessage(TypedDict):
    v: Literal["0.1"]
    type: Literal["hello"]
    session_id: str
    client: NotRequired[ClientInfo]


class ByeMessage(TypedDict):
    v: Literal["0.1"]
    type: Literal["bye"]
    session_id: str


class StateMessage(TypedDict):
    v: Literal["0.1"]
    type: Literal["state"]
    seq: int
    state: State
    timings: NotRequired[dict[str, object]]


class PlayMessage(TypedDict):
    v: Literal["0.1"]
    type: Literal["play"]
    seq: int
    play: Action | None
    playable: NotRequired[list[int]]
    model: NotRequired[ModelRef]
    timings: NotRequired[dict[str, object]]


class ErrorInfo(TypedDict):
    code: str
    message: str


class ErrorMessage(TypedDict):
    v: Literal["0.1"]
    type: Literal["error"]
    seq: NotRequired[int]
    error: ErrorInfo


class FrameCaps(TypedDict, total=False):
    formats: list[ImageFormat]
    max_bytes: int


class Retention(TypedDict, total=False):
    requires_consent: bool


class Capabilities(TypedDict):
    vision: bool
    play: bool
    actions: list[ActionType]
    state_schema: str
    frame: NotRequired[FrameCaps]
    max_hz: NotRequired[float]
    models: NotRequired[list[ModelRef]]
    retention: NotRequired[Retention]


class HelloAck(TypedDict):
    v: Literal["0.1"]
    type: Literal["hello_ack"]
    capabilities: Capabilities


ClientMessage = FrameMessage | HelloMessage | ByeMessage
ServerMessage = StateMessage | PlayMessage | ErrorMessage | HelloAck
Message = ClientMessage | ServerMessage
