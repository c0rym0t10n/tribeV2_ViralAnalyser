"""Score math, signal-shape helpers, dataclasses, and the video-info reader.

Owns the numeric primitives the engine builds metric scores out of: ratio /
value scoring, novelty + activation aggregates, smoothing, normalisation,
SVG point projection. Also owns the ``ReviewMetric`` / ``SpeechMetric``
dataclasses so downstream modules can import them from a stable location.

``_read_video_info`` lazy-imports ``moviepy`` so this module stays importable
in the CI light tier (numpy + matplotlib only).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from analysis_settings import AnalysisModeProfile  # noqa: F401  (used by callers via types)

# ``_metric_display`` formats a friendly label for an arbitrary score-like
# item; the friendly-label table itself lives in ``copy_ru``. The reverse
# import (``copy_ru`` → ``metrics``) is gated behind ``TYPE_CHECKING``, so
# this stays acyclic at runtime.
from tribe_review.copy_ru import _friendly_metric_label


@dataclass
class ReviewMetric:
    key: str
    label: str
    score: int
    summary: str
    raw_value: float


@dataclass
class SpeechMetric:
    key: str
    label: str
    value: str
    summary: str


def _read_video_info(video_path: str | Path) -> dict[str, Any]:
    # Lazy-import moviepy so the engine stays importable without it (CI light
    # tier, snapshot tests). Production callers pay this cost once per review.
    import moviepy as mpy

    clip = mpy.VideoFileClip(str(video_path))
    try:
        return {
            "filename": Path(video_path).name,
            "duration_seconds": round(float(clip.duration or 0.0), 2),
            "fps": round(float(clip.fps or 0.0), 2),
            "resolution": f"{clip.w}x{clip.h}",
        }
    finally:
        clip.close()


def _early_ratio(activation: np.ndarray) -> float:
    split = max(1, len(activation) // 4)
    return float((np.mean(activation[:split]) + 1e-6) / (np.mean(activation[split:]) + 1e-6))


def _sustain_ratio(activation: np.ndarray) -> float:
    third = max(1, len(activation) // 3)
    return float((np.mean(activation[-third:]) + 1e-6) / (np.mean(activation[:third]) + 1e-6))


def _transition_density(novelty: np.ndarray) -> float:
    if len(novelty) < 3:
        return 0.0
    centered = (novelty - novelty.mean()) / (novelty.std() + 1e-6)
    return float(int(np.sum(centered > 0.6)) / len(novelty))


def _signal_stability(novelty: np.ndarray) -> float:
    return float(1.0 / (1.0 + np.std(novelty) / (np.mean(novelty) + 1e-6)))


def _activation_density(activation: np.ndarray) -> float:
    return float(np.mean(activation) / (np.percentile(activation, 90) + 1e-6))


def _score_from_ratio(value: float, center: float, spread: float) -> int:
    return _clip_score(50 + 28 * ((value - center) / max(spread, 1e-6)))


def _score_from_value(value: float, center: float, spread: float) -> int:
    return _clip_score(50 + 28 * ((value - center) / max(spread, 1e-6)))


def _clip_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _format_ts(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def _normalize_series(values: np.ndarray) -> np.ndarray:
    low = float(np.min(values))
    high = float(np.max(values))
    return np.full_like(values, 50.0, dtype=float) if high - low < 1e-6 else 100.0 * (values - low) / (high - low)


def _compound_signal(activation: np.ndarray, novelty: np.ndarray) -> np.ndarray:
    activation_score = _normalize_series(activation)
    novelty_score = _normalize_series(novelty)
    return np.clip(0.7 * activation_score + 0.3 * novelty_score, 0.0, 100.0)


def _smooth_series(values: np.ndarray, window: int = 5) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) <= 2:
        return values
    usable_window = min(window, len(values) if len(values) % 2 == 1 else len(values) - 1)
    usable_window = max(3, usable_window)
    if usable_window <= 1 or usable_window > len(values):
        return values
    kernel = np.ones(usable_window, dtype=float) / usable_window
    padded = np.pad(values, (usable_window // 2, usable_window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def _pick_extreme_index(values: np.ndarray, indices: list[int], mode: str) -> int:
    if not indices:
        indices = list(range(len(values)))
    subset = np.asarray([values[index] for index in indices], dtype=float)
    local = int(np.argmax(subset) if mode == "max" else np.argmin(subset))
    return int(indices[local])


def _build_svg_points(values: np.ndarray, width: int = 860, height: int = 210, padding: int = 18) -> str:
    return " ".join(f"{_svg_xy(index, values, width, height, padding)[0]:.2f},{_svg_xy(index, values, width, height, padding)[1]:.2f}" for index in range(len(values))) if len(values) else ""


def _svg_xy(index: int, values: np.ndarray, width: int, height: int, padding: int) -> tuple[float, float]:
    x = width / 2.0 if len(values) == 1 else padding + (width - 2 * padding) * (index / (len(values) - 1))
    y = height - padding - (height - 2 * padding) * (float(values[index]) / 100.0)
    return x, y


def _metric_key(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("key") or "")
    return str(getattr(item, "key", "") or "")


def _metric_score(item: Any) -> int:
    if isinstance(item, dict):
        return int(item.get("score") or 0)
    return int(getattr(item, "score", 0) or 0)


def _metric_display(item: Any) -> str:
    key = _metric_key(item)
    fallback = str(item.get("label") if isinstance(item, dict) else getattr(item, "label", "")) or key
    return _friendly_metric_label(key, fallback).lower()


def _metric_scores(metrics: list[Any]) -> dict[str, int]:
    return {_metric_key(metric): _metric_score(metric) for metric in metrics}


def _pick_template(candidates: list[tuple[bool, str]], fallback: str) -> str:
    for condition, text in candidates:
        if condition:
            return text
    return fallback
