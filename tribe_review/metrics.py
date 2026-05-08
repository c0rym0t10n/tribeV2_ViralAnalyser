"""Metric dataclasses, score helpers and signal-shape math.

Currently re-exports from :mod:`tribe_review._engine`. Function bodies will
migrate here in a follow-up PR.
"""

from __future__ import annotations

from tribe_review._engine import (
    FocusWindow,
    ReviewMetric,
    SpeechMetric,
    _activation_density,
    _build_svg_points,
    _clip_score,
    _compound_signal,
    _drop_timestamps,
    _early_ratio,
    _find_drop_indices,
    _focus_valid_indices,
    _format_ts,
    _metric_display,
    _metric_key,
    _metric_score,
    _metric_scores,
    _normalize_series,
    _pick_extreme_index,
    _pick_template,
    _read_video_info,
    _score_from_ratio,
    _score_from_value,
    _signal_stability,
    _smooth_series,
    _speech_line,
    _sustain_ratio,
    _svg_xy,
    _transition_density,
)

__all__ = [
    "FocusWindow",
    "ReviewMetric",
    "SpeechMetric",
    "_activation_density",
    "_build_svg_points",
    "_clip_score",
    "_compound_signal",
    "_drop_timestamps",
    "_early_ratio",
    "_find_drop_indices",
    "_focus_valid_indices",
    "_format_ts",
    "_metric_display",
    "_metric_key",
    "_metric_score",
    "_metric_scores",
    "_normalize_series",
    "_pick_extreme_index",
    "_pick_template",
    "_read_video_info",
    "_score_from_ratio",
    "_score_from_value",
    "_signal_stability",
    "_smooth_series",
    "_speech_line",
    "_sustain_ratio",
    "_svg_xy",
    "_transition_density",
]
