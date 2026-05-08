"""TRIBE review engine — orchestrator.

Stage-2 / G2 left this module with a single entrypoint, ``generate_review``,
plus the imports it needs from the thematic modules
(:mod:`tribe_review.copy_ru`, :mod:`~.metrics`, :mod:`~.timeline`,
:mod:`~.recommendations`, :mod:`~.comparison`). The fan-out happened so that
later passes (G3 conditional-copy localisation, G4 ollama trimming) can
operate on smaller, topic-shaped surfaces.

The heavy runtime dependencies (``torch`` via ``tribe_runtime`` /
``speech_runtime``, ``moviepy`` via ``_read_video_info``) are kept off the
import path: the first two are gated behind ``TYPE_CHECKING``; the third is
lazy-imported inside :func:`tribe_review.metrics._read_video_info`. This
keeps the engine importable in the CI light tier.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from analysis_settings import get_analysis_mode_profile

from tribe_review.copy_ru import (
    _metric_label,
    _signal_note,
)
from report_localization import metric_band_summary
from tribe_review.metrics import (
    ReviewMetric,
    _activation_density,
    _early_ratio,
    _read_video_info,
    _score_from_ratio,
    _score_from_value,
    _signal_stability,
    _sustain_ratio,
    _transition_density,
)
from tribe_review.recommendations import (
    _build_action_items,
    _build_executive_summary,
    _build_product_summary,
    _build_recommendation_plan,
    _build_recommendations,
    _build_strengths,
    _build_verdict,
    _build_weaknesses,
)
from tribe_review.timeline import (
    _build_drop_moments,
    _build_focus_windows,
    _build_phase_notes,
    _build_seek_targets,
    _build_speech_layer,
    _build_timeline,
    _find_drop_indices,
)

if TYPE_CHECKING:
    # Heavy runtime modules (torch, tribev2, whisper) are only needed by the
    # production callers. The engine itself manipulates numpy arrays and plain
    # dicts, so we keep the type names visible to type-checkers / IDEs but
    # avoid importing the underlying packages at runtime.
    from speech_runtime import SpeechRunResult  # noqa: F401
    from tribe_runtime import TribeRunResult  # noqa: F401


def generate_review(
    video_path: str | Path,
    run: TribeRunResult,
    speech: SpeechRunResult | None = None,
    speech_error: str | None = None,
    analysis_mode: str | None = None,
    variant_name: str | None = None,
    language: str = "ru",
) -> dict[str, Any]:
    profile = get_analysis_mode_profile(analysis_mode)
    preds = np.asarray(run.preds)
    if preds.ndim != 2 or preds.shape[0] < 2:
        raise ValueError("TRIBE returned too few samples for a useful review.")

    info = _read_video_info(video_path)
    info["title"] = variant_name or Path(video_path).stem
    activation = np.mean(np.abs(preds), axis=1)
    novelty = np.zeros_like(activation)
    novelty[1:] = np.linalg.norm(np.diff(preds, axis=0), axis=1)

    early_ratio = _early_ratio(activation)
    sustain_ratio = _sustain_ratio(activation)
    transition_density = _transition_density(novelty)
    signal_stability = _signal_stability(novelty)
    activation_density = _activation_density(activation)

    # specs: ``(metric_key, score, raw_value)`` per metric. The pre-G3 5-tuple
    # also carried a hardcoded RU label and the ternary ``_*_summary`` strings,
    # but both were unpacked into discard slots — ``label`` is computed by
    # ``_metric_label`` and ``summary`` by ``_metric_summary``. G3 dropped
    # those dead slots and the corresponding ``_early_response_summary`` etc.
    # ternary helpers.
    specs = [
        ("early_response", _score_from_ratio(early_ratio, 1.05, 0.35), early_ratio),
        ("sustain", _score_from_ratio(sustain_ratio, 0.95, 0.30), sustain_ratio),
        ("transition", _score_from_value(transition_density, 0.22, 0.16), transition_density),
        ("stability", _score_from_value(signal_stability, 0.58, 0.20), signal_stability),
        ("density", _score_from_value(activation_density, 0.72, 0.18), activation_density),
    ]
    metrics = [
        ReviewMetric(
            key=key,
            label=_metric_label(key, profile),
            score=score,
            summary=metric_band_summary(key, score, language=language),
            raw_value=round(float(raw_value), 3),
        )
        for key, score, raw_value in specs
    ]

    drop_indices = _find_drop_indices(run.timestamps, activation, novelty, profile)
    drop_moments = _build_drop_moments(run.timestamps, drop_indices, profile)
    speech_layer = _build_speech_layer(info["duration_seconds"], speech, speech_error, profile, language=language)
    recommendations = _build_recommendations(metrics, drop_moments, info["duration_seconds"], speech_layer, profile)

    overall_score = int(round(sum(metric.score for metric in metrics) / len(metrics)))
    metric_lookup = {metric.key: metric.score for metric in metrics}
    ordered_metrics = sorted(metrics, key=lambda item: item.score, reverse=True)
    top_metric = ordered_metrics[0]
    weak_metric = ordered_metrics[-1]
    runner_metric = ordered_metrics[1]
    timeline = _build_timeline(run.timestamps, activation, novelty, drop_indices)
    focus_windows = _build_focus_windows(run.timestamps, activation, novelty, profile)

    return {
        "mode": "single",
        "title": info["title"],
        "variant_name": info["title"],
        "overall_score": overall_score,
        "verdict": _build_verdict(overall_score, ordered_metrics, profile),
        "executive_summary": _build_executive_summary(overall_score, top_metric, weak_metric, runner_metric, speech_layer, profile),
        "product_summary": _build_product_summary(overall_score, ordered_metrics, speech_layer, profile),
        "strengths": _build_strengths(ordered_metrics, speech_layer, profile),
        "weaknesses": _build_weaknesses(ordered_metrics, speech_layer, profile),
        "metrics": [metric.__dict__ for metric in metrics],
        "metric_lookup": metric_lookup,
        "drop_moments": drop_moments,
        "recommendations": recommendations,
        "recommendation_plan": _build_recommendation_plan(recommendations, top_metric, weak_metric, profile),
        "action_items": _build_action_items(recommendations, focus_windows, drop_moments, speech_layer, metrics, profile),
        "video": info,
        "device": run.device,
        "modalities": run.modalities,
        "analysis_mode": {
            "key": profile.key,
            "label": profile.label,
            "short_label": profile.short_label,
            "description": profile.description,
            "note": profile.ui_note,
        },
        "signal_note": _signal_note(profile),
        "speech": speech_layer,
        "timeline": timeline,
        "focus_windows": [window.__dict__ for window in focus_windows],
        "phase_notes": _build_phase_notes(activation),
        "seek_targets": _build_seek_targets(focus_windows, drop_moments, speech_layer),
    }
