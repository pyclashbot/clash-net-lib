"""Fixture vocabulary.

This is a deliberately small baseline: only the names used by the conformance fixtures.
The full card/unit vocabulary is a later, generated artifact. The version/hash pair lets
a state declare which vocabulary produced it without pinning model class indices here.
"""

from __future__ import annotations

import hashlib
import json

from .types import VocabRef

VOCAB_VERSION = "fixtures-0.1"

BASELINE_CARDS: tuple[str, ...] = (
    "Balloon",
    "Fireball",
    "Hog Rider",
    "Log",
    "Mega Knight",
    "Royal Giant",
    "Skeleton King",
    "Snowball",
)

BASELINE_UNITS: tuple[str, ...] = (
    "Balloon",
    "Hog Rider",
    "Mega Knight",
    "Royal Giant",
    "Skeleton King",
)


def _payload() -> dict[str, list[str]]:
    return {"cards": sorted(BASELINE_CARDS), "units": sorted(BASELINE_UNITS)}


def _compute_hash() -> str:
    canonical = json.dumps(_payload(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


VOCAB_HASH = _compute_hash()


def vocab_ref() -> VocabRef:
    """Return the ``{version, hash}`` pair to put on a state."""
    return {"version": VOCAB_VERSION, "hash": VOCAB_HASH}
