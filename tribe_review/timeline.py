"""Timeline construction, focus windows, drop moments, and the speech layer.

Owns the temporal-shape outputs of a review: the ``points`` array drawn on
the chart, focus / weak / dynamic windows, drop markers, phase notes, and the
speech-layer dict. ``_focus_valid_indices`` and ``_find_drop_indices`` live
here too — they're consumed downstream by ``_build_focus_windows`` /
``_build_drop_moments`` so co-locating them avoids a metrics → timeline
cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from analysis_settings import AnalysisModeProfile

from report_localization import speech_metric_summary

from tribe_review.metrics import (
    SpeechMetric,
    _build_svg_points,
    _compound_signal,
    _format_ts,
    _normalize_series,
    _pick_extreme_index,
    _smooth_series,
    _svg_xy,
)

if TYPE_CHECKING:
    from speech_runtime import SpeechRunResult  # noqa: F401


@dataclass
class FocusWindow:
    label: str
    timestamp: str
    seconds: float
    summary: str


def _build_speech_layer(
    duration_seconds: float,
    speech: SpeechRunResult | None,
    speech_error: str | None,
    profile: AnalysisModeProfile,
    language: str = "ru",
) -> dict[str, Any]:
    if speech_error:
        return {
            "available": False,
            "title": "Speech layer",
            "message": f"Транскрипция не поднялась: {speech_error}",
            "note": "Это отдельная локальная транскрипция Whisper. Она помогает сопоставлять слабые места графика с конкретными фразами и паузами.",
            "metrics": [],
            "text": "",
            "segments": [],
            "language": None,
            "model_name": None,
            "word_count": 0,
            "segment_count": 0,
            "speech_start_seconds": None,
            "pause_ratio": None,
        }

    if speech is None or not speech.words:
        return {
            "available": False,
            "title": "Speech layer",
            "message": "Надёжная речь не обнаружена. В текущем режиме строгости блок речи лучше скрыть, чем показать случайную галлюцинацию ASR.",
            "note": f"Отдельная локальная транскрипция Whisper. Сейчас включён режим «{profile.label}»: {profile.ui_note.lower()}",
            "metrics": [],
            "text": "",
            "segments": [],
            "language": getattr(speech, "language", None),
            "model_name": getattr(speech, "model_name", None),
            "word_count": 0,
            "segment_count": 0,
            "speech_start_seconds": None,
            "pause_ratio": None,
        }

    active_duration = max(1e-6, sum(max(0.0, word.end - word.start) for word in speech.words))
    first_start = float(speech.words[0].start)
    pauses = [max(0.0, current.start - previous.end) for previous, current in zip(speech.words, speech.words[1:])]
    long_pause_total = sum(gap for gap in pauses if gap >= 0.45)
    pace = len(speech.words) / max(duration_seconds, 1e-6)
    articulation = len(speech.words) / active_duration
    confidence = float(np.mean([word.probability for word in speech.words]))
    pause_ratio = long_pause_total / max(duration_seconds, 1e-6)

    # Note: speech-metric LABELS stay Russian even when language="en" — the
    # F3 ``localize_report`` post-processor (specifically
    # ``_speech_metric_label_en``) rewrites them into English at the report
    # level. Direct EN labels in the engine would break that pipeline.
    metrics = [
        SpeechMetric("speech_start", "Старт речи", f"{first_start:.2f} c", speech_metric_summary("speech_start", first_start, language=language)),
        SpeechMetric("speech_pace", "Слов в секунду", f"{pace:.2f}", speech_metric_summary("speech_pace", pace, language=language)),
        SpeechMetric("articulation", "Насколько плотно сказано", f"{articulation:.2f}", speech_metric_summary("articulation", articulation, language=language)),
        SpeechMetric("pause_ratio", "Доля пауз", f"{pause_ratio:.2f}", speech_metric_summary("pause_ratio", pause_ratio, language=language)),
        SpeechMetric("confidence", "Уверенность ASR", f"{confidence:.2f}", speech_metric_summary("confidence", confidence, language=language)),
    ]
    segments = [{"start": round(segment.start, 2), "end": round(segment.end, 2), "text": segment.text} for segment in speech.segments]

    return {
        "available": True,
        "title": "Speech layer",
        "message": None,
        "note": f"Отдельная локальная транскрипция Whisper в режиме «{profile.label}». Она помогает проверить, какие слова и паузы совпадают со слабыми местами графика.",
        "metrics": [metric.__dict__ for metric in metrics],
        "text": speech.text,
        "segments": segments,
        "language": speech.language,
        "model_name": speech.model_name,
        "word_count": len(speech.words),
        "segment_count": len(segments),
        "speech_start_seconds": round(first_start, 2),
        "pause_ratio": round(pause_ratio, 3),
    }


def _build_timeline(
    timestamps: list[float],
    activation: np.ndarray,
    novelty: np.ndarray,
    drop_indices: list[int],
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    activation_score = _normalize_series(activation)
    novelty_score = _normalize_series(novelty)
    compound = np.clip(0.7 * activation_score + 0.3 * novelty_score, 0.0, 100.0)

    for index, ts in enumerate(timestamps):
        points.append(
            {
                "seconds": round(float(ts), 2),
                "timestamp": _format_ts(ts),
                "activation": round(float(activation[index]), 4),
                "novelty": round(float(novelty[index]), 4),
                "signal_score": round(float(compound[index]), 1),
            }
        )

    svg_points = _build_svg_points(compound)
    marker_points = []
    for index in drop_indices:
        if 0 <= index < len(points):
            x, y = _svg_xy(index, compound, width=860, height=210, padding=18)
            marker_points.append(
                {
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "timestamp": points[index]["timestamp"],
                    "seconds": points[index]["seconds"],
                }
            )

    return {
        "points": points,
        "svg_points": svg_points,
        "markers": marker_points,
        "max_score": round(float(np.max(compound)), 1),
        "avg_score": round(float(np.mean(compound)), 1),
        "min_score": round(float(np.min(compound)), 1),
    }


def _build_phase_notes(activation: np.ndarray) -> list[str]:
    chunks = np.array_split(activation, 3)
    labels = ["Старт", "Середина", "Финал"]
    summaries: list[str] = []
    baseline = float(np.mean(activation) + 1e-6)
    for label, chunk in zip(labels, chunks):
        ratio = float(np.mean(chunk) / baseline)
        if ratio >= 1.08:
            summaries.append(f"{label}: выше среднего по ролику. Здесь сигнал держится уверенно.")
        elif ratio >= 0.92:
            summaries.append(f"{label}: близко к среднему уровню. Без сильного усиления и без явной просадки.")
        else:
            summaries.append(f"{label}: ниже среднего по ролику. Есть смысл посмотреть монтаж и подачу именно в этой фазе.")
    return summaries


def _build_seek_targets(focus_windows: list[FocusWindow], drop_moments: list[dict[str, Any]], speech_layer: dict[str, Any]) -> list[dict[str, Any]]:
    targets = [
        {"label": item.label, "timestamp": item.timestamp, "seconds": item.seconds, "kind": "focus", "summary": item.summary}
        for item in focus_windows
    ]
    for item in drop_moments:
        targets.append({"label": "Подозрительный момент", "timestamp": item["timestamp"], "seconds": item["seconds"], "kind": "drop", "summary": item["reason"]})
    for segment in speech_layer.get("segments", [])[:6]:
        targets.append({"label": "Speech segment", "timestamp": _format_ts(segment["start"]), "seconds": segment["start"], "kind": "speech", "summary": segment["text"]})
    return targets


def _find_drop_indices(
    timestamps: list[float],
    activation: np.ndarray,
    novelty: np.ndarray,
    profile: AnalysisModeProfile,
) -> list[int]:
    act_z = (activation - activation.mean()) / (activation.std() + 1e-6)
    nov_z = (novelty - novelty.mean()) / (novelty.std() + 1e-6)
    valid_indices = set(_focus_valid_indices(timestamps))
    indices = [
        index
        for index in range(1, len(activation))
        if index in valid_indices
        and act_z[index] < profile.drop_activation_z_threshold
        and nov_z[index] < profile.drop_novelty_z_threshold
    ]
    return indices[: profile.max_drop_markers]


def _drop_timestamps(drop_moments: list[dict[str, Any]], limit: int = 3) -> str:
    values = [str(item.get("timestamp") or "").strip() for item in drop_moments if item.get("timestamp")]
    return ", ".join(values[:limit])


def _speech_line(speech_layer: dict[str, Any]) -> str:
    if speech_layer.get("available"):
        start = speech_layer.get("speech_start_seconds")
        if isinstance(start, (int, float)) and float(start) > 2.0:
            return f"Речь распознана, но первая значимая фраза начинается только около {float(start):.1f} с, поэтому старт лучше проверить отдельно."
        return "Речь распознана: слабые места можно сверять не только по кадру, но и по словам рядом с ними."
    return "Речь сейчас не даёт надежной опоры, поэтому выводы лучше читать через монтаж, кадр и звук."


def _build_focus_windows(
    timestamps: list[float],
    activation: np.ndarray,
    novelty: np.ndarray,
    profile: AnalysisModeProfile,
) -> list[FocusWindow]:
    del profile
    if not timestamps:
        return []
    compound = _compound_signal(activation, novelty)
    smoothed_compound = _smooth_series(compound, window=5)
    smoothed_novelty = _smooth_series(novelty, window=3)
    valid_indices = _focus_valid_indices(timestamps)

    strongest_idx = _pick_extreme_index(smoothed_compound, valid_indices, mode="max")
    weakest_idx = _pick_extreme_index(smoothed_compound, valid_indices, mode="min")

    dynamic_candidates = [index for index in valid_indices if index > 0]
    if not dynamic_candidates:
        dynamic_candidates = list(range(1, len(timestamps))) or [0]
    dynamic_idx = _pick_extreme_index(smoothed_novelty, dynamic_candidates, mode="max")
    return [
        FocusWindow("Лучший участок", _format_ts(timestamps[strongest_idx]), round(float(timestamps[strongest_idx]), 2), "Здесь график выше соседних точек. Используй этот момент как ориентир по кадру, темпу и крупности."),
        FocusWindow("Слабое окно", _format_ts(timestamps[weakest_idx]), round(float(timestamps[weakest_idx]), 2), "Здесь график проседает относительно соседних точек. Проверь, не затянут ли план и не потерялся ли главный объект."),
        FocusWindow("Резкая смена", _format_ts(timestamps[dynamic_idx]), round(float(timestamps[dynamic_idx]), 2), "Здесь график меняется сильнее всего. Проверь, помогает ли переход удержать внимание или выглядит случайным скачком."),
    ]


def _build_drop_moments(timestamps: list[float], indices: list[int], profile: AnalysisModeProfile) -> list[dict[str, Any]]:
    del profile
    return [
        {
            "seconds": round(float(timestamps[index]), 2),
            "timestamp": _format_ts(float(timestamps[index])),
            "reason": "локальная просадка графика",
        }
        for index in indices
        if 0 <= index < len(timestamps)
    ]


def _focus_valid_indices(timestamps: list[float]) -> list[int]:
    if len(timestamps) <= 4:
        return list(range(len(timestamps)))

    start = float(timestamps[0])
    end = float(timestamps[-1])
    duration = max(0.0, end - start)
    edge_buffer = max(3.0, min(4.0, duration * 0.04))
    if duration <= 8.0:
        edge_buffer = min(0.8, max(0.35, duration * 0.05))

    tail_buffer = 5.0 if duration > 8.0 else max(1.0, duration * 0.30)
    upper_bound = end - tail_buffer
    candidates = [
        index
        for index, ts in enumerate(timestamps)
        if (start + edge_buffer) < float(ts) < upper_bound
    ]
    if len(candidates) >= 3:
        return candidates

    middle = [
        index
        for index, ts in enumerate(timestamps[1:-1], start=1)
        if float(ts) <= upper_bound
    ]
    return middle or list(range(len(timestamps)))
