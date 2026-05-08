"""Synthetic stand-ins for TRIBE / Whisper runtime results.

CI's light tier deliberately skips installing ``torch``, ``tribev2``,
``whisper`` and ``moviepy`` (they pull a multi-GB CUDA stack and the TRIBE
checkpoint). ``tribe_review._engine`` only reads attributes off these objects,
so this module fabricates small, deterministic numpy-backed dataclasses with
the exact attribute surface the engine actually touches:

* ``run.preds`` — 2D ``numpy.ndarray`` ``(timesteps, features)``
* ``run.timestamps`` — ``list[float]``
* ``run.device`` — ``str``
* ``run.modalities`` — ``list[str]``
* ``speech.words`` — list of objects exposing ``start`` / ``end`` / ``probability``
* ``speech.segments`` — list of objects exposing ``start`` / ``end`` / ``text``
* ``speech.text`` — ``str``
* ``speech.language`` — ``str | None``
* ``speech.model_name`` — ``str | None``

Anything beyond that surface (model handles, raw audio, etc.) is not consumed
by the engine and is intentionally omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SyntheticWord:
    """Stand-in for ``speech_runtime.WhisperWord``."""

    start: float
    end: float
    probability: float


@dataclass
class SyntheticSegment:
    """Stand-in for ``speech_runtime.WhisperSegment``."""

    start: float
    end: float
    text: str


@dataclass
class SyntheticSpeechRun:
    """Stand-in for ``speech_runtime.SpeechRunResult``."""

    words: list[SyntheticWord]
    segments: list[SyntheticSegment]
    text: str
    language: str | None
    model_name: str | None


@dataclass
class SyntheticTribeRun:
    """Stand-in for ``tribe_runtime.TribeRunResult``."""

    preds: Any  # ``numpy.ndarray[float64]`` of shape ``(T, F)``
    timestamps: list[float]
    device: str
    modalities: list[str]


def make_synthetic_tribe_run(
    *,
    timesteps: int = 8,
    features: int = 4,
    seed: int = 1234,
    early_strong: bool = True,
) -> SyntheticTribeRun:
    """Return a small but realistic TRIBE result.

    Defaults: 8 timestamps spaced 1 s apart, 4 latent features, deterministic
    via numpy seed. ``early_strong=True`` builds a curve weighted toward the
    first quarter (drives a positive ``early_response`` score). Flipping it to
    ``False`` produces a back-loaded curve so the comparison fixture can
    contrast two variants with different metric profiles.
    """
    rng = np.random.default_rng(seed)
    base = rng.normal(loc=0.0, scale=0.4, size=(timesteps, features))
    if early_strong:
        envelope = np.linspace(1.4, 0.6, timesteps)
    else:
        envelope = np.linspace(0.6, 1.4, timesteps)
    preds = base * envelope[:, None]
    return SyntheticTribeRun(
        preds=preds,
        timestamps=[float(i) for i in range(timesteps)],
        device="cpu",
        modalities=["video", "audio"],
    )


def make_synthetic_speech_run() -> SyntheticSpeechRun:
    """Return a small Whisper-shaped speech result with a few words + segments."""
    words = [
        SyntheticWord(start=0.40, end=0.70, probability=0.92),
        SyntheticWord(start=0.80, end=1.20, probability=0.88),
        SyntheticWord(start=1.40, end=1.90, probability=0.81),
        SyntheticWord(start=2.60, end=3.10, probability=0.76),
        SyntheticWord(start=3.40, end=3.90, probability=0.84),
        SyntheticWord(start=4.50, end=5.00, probability=0.79),
    ]
    segments = [
        SyntheticSegment(start=0.40, end=1.90, text="Привет, это первый сегмент."),
        SyntheticSegment(start=2.60, end=5.00, text="Здесь второй сегмент с паузой."),
    ]
    return SyntheticSpeechRun(
        words=words,
        segments=segments,
        text="Привет, это первый сегмент. Здесь второй сегмент с паузой.",
        language="ru",
        model_name="whisper-tiny",
    )


def synthetic_video_info(filename: str = "synthetic.mp4") -> dict[str, Any]:
    """Pre-baked ``_read_video_info`` payload that bypasses moviepy.

    The engine's real ``_read_video_info`` needs a decoded video to extract
    ``duration``, ``fps``, ``w``, ``h``. In tests we stub it via monkeypatch,
    handing back this dict instead. Values are picked to land in the
    ``duration_seconds > 7.0`` branch of ``_comparison_usable_end`` so the
    comparison golden exercises the trimmed-window path.
    """
    return {
        "filename": filename,
        "duration_seconds": 7.0,
        "fps": 30.0,
        "resolution": "1080x1920",
    }
