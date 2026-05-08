"""TRIBE review engine internals.

Consolidated from the legacy ``review_engine.py``: the original file had
multiple top-level definitions for the same function (``_build_action_items``,
``_focus_valid_indices``, ``_action_copy_for_metric``, ``_action_metric_candidates``,
``_metric_label``, ``_metric_summary``, ``_signal_note``, ``_build_focus_windows``,
``_build_strengths``, ``_build_weaknesses``, ``_build_product_summary``,
``_build_executive_summary``, ``_build_recommendation_plan``, ``_build_drop_moments``,
``_build_recommendations``, ``_build_simple_recommendations``, ``_build_verdict``,
``_build_comparison_rows``, ``_build_axis_winners``, ``_build_common_gaps``,
``_build_ranking``, ``_variant_compare_summary``, ``_build_compare_verdict``,
``_build_compare_executive_summary``, ``_build_compare_product_summary``,
``_build_comparison_recommendations``, ``_simple_metric_action``); Python uses the
last def, so all earlier copies were dead code. They have been removed here.

The thematic split (metrics, recommendations, comparison, timeline, copy_ru)
lives in sibling modules; each is currently a thin re-export of this engine
module so that downstream code can ``from tribe_review.metrics import ...``.
A future PR will migrate the function bodies themselves once a snapshot test
fixture is in place.
"""
from __future__ import annotations


from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


import moviepy as mpy
import numpy as np


from analysis_settings import AnalysisModeProfile, get_analysis_mode_profile
from speech_runtime import SpeechRunResult
from tribe_runtime import TribeRunResult


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


@dataclass
class FocusWindow:
    label: str
    timestamp: str
    seconds: float
    summary: str


def generate_review(
    video_path: str | Path,
    run: TribeRunResult,
    speech: SpeechRunResult | None = None,
    speech_error: str | None = None,
    analysis_mode: str | None = None,
    variant_name: str | None = None,
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

    specs = [
        ("early_response", "Ранний отклик", _score_from_ratio(early_ratio, 1.05, 0.35), _early_response_summary(_score_from_ratio(early_ratio, 1.05, 0.35)), early_ratio),
        ("sustain", "Устойчивость отклика", _score_from_ratio(sustain_ratio, 0.95, 0.30), _sustain_summary(_score_from_ratio(sustain_ratio, 0.95, 0.30)), sustain_ratio),
        ("transition", "Плотность переходов", _score_from_value(transition_density, 0.22, 0.16), _transition_summary(_score_from_value(transition_density, 0.22, 0.16)), transition_density),
        ("stability", "Стабильность сигнала", _score_from_value(signal_stability, 0.58, 0.20), _stability_summary(_score_from_value(signal_stability, 0.58, 0.20)), signal_stability),
        ("density", "Плотность активации", _score_from_value(activation_density, 0.72, 0.18), _density_summary(_score_from_value(activation_density, 0.72, 0.18)), activation_density),
    ]
    metrics = [
        ReviewMetric(
            key=key,
            label=_metric_label(key, profile),
            score=score,
            summary=_metric_summary(key, score, profile),
            raw_value=round(float(raw_value), 3),
        )
        for key, _label, score, _summary, raw_value in specs
    ]

    drop_indices = _find_drop_indices(run.timestamps, activation, novelty, profile)
    drop_moments = _build_drop_moments(run.timestamps, drop_indices, profile)
    speech_layer = _build_speech_layer(info["duration_seconds"], speech, speech_error, profile)
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


def generate_comparison_report(reviews: list[dict[str, Any]], analysis_mode: str | None = None) -> dict[str, Any]:
    if len(reviews) < 2:
        raise ValueError("Need at least two reviews to compare.")
    profile = get_analysis_mode_profile(analysis_mode)

    variants = []
    for index, review in enumerate(reviews, start=1):
        variant = dict(review)
        variant["variant_key"] = variant.get("variant_key") or f"v{index}"
        variants.append(variant)
    variants = _prepare_comparison_variants(variants)

    ranked = sorted(
        variants,
        key=lambda item: (
            item.get("comparison_score", item["overall_score"]),
            item.get("comparison_early_avg", 0),
            item.get("comparison_signal_avg", 0),
            item["metric_lookup"].get("sustain", 0),
        ),
        reverse=True,
    )
    best = ranked[0]
    runner_up = ranked[1]
    comparison_rows = _build_comparison_rows(ranked)
    axis_winners = _build_axis_winners(comparison_rows)
    common_gaps = _build_common_gaps(ranked, profile)

    return {
        "mode": "compare",
        "title": f"Сравнение {len(ranked)} версий",
        "variant_count": len(ranked),
        "best_variant_key": best["variant_key"],
        "best_variant_name": best["title"],
        "overall_score": best.get("comparison_score", best["overall_score"]),
        "verdict": _build_compare_verdict(best, runner_up, len(ranked)),
        "executive_summary": _build_compare_executive_summary(best, runner_up, axis_winners, profile),
        "product_summary": _build_compare_product_summary(best, runner_up, common_gaps, profile),
        "recommendations": _build_comparison_recommendations(best, runner_up, common_gaps),
        "analysis_mode": {
            "key": profile.key,
            "label": profile.label,
            "short_label": profile.short_label,
            "description": profile.description,
            "note": profile.ui_note,
            "comparison_note": profile.comparison_spread_note,
        },
        "ranking": _build_ranking(ranked, best),
        "axis_winners": axis_winners,
        "common_gaps": common_gaps,
        "comparison_rows": comparison_rows,
        "variants": ranked,
        "signal_note": "Сравнение строится по одному расчетному графику для всех версий. Выигрывает не разовый пик, а версия с более сильным стартом, более высоким средним уровнем и меньшим числом резких просадок.",
    }


def _prepare_comparison_variants(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable_ends = [_comparison_usable_end(variant) for variant in variants]
    positive_ends = [end for end in usable_ends if end > 0]
    common_end = min(positive_ends) if positive_ends else 0.0
    common_end = max(common_end, 1.0)

    prepared: list[dict[str, Any]] = []
    for variant, usable_end in zip(variants, usable_ends):
        item = dict(variant)
        original_score = int(round(float(item.get("overall_score") or 0)))
        item["analysis_score"] = original_score
        comparison = _comparison_signal_score(item, common_end, usable_end)
        item.update(comparison)
        item["overall_score"] = comparison["comparison_score"]
        prepared.append(item)
    return prepared


def _comparison_usable_end(variant: dict[str, Any]) -> float:
    timeline_points = ((variant.get("timeline") or {}).get("points") or [])
    timeline_end = max((float(point.get("seconds") or 0.0) for point in timeline_points if isinstance(point, dict)), default=0.0)
    video = variant.get("video") if isinstance(variant.get("video"), dict) else {}
    duration = float(video.get("duration_seconds") or timeline_end or 0.0)
    end = max(timeline_end, duration)
    if end > 7.0:
        return max(1.0, end - 5.0)
    return max(1.0, end)


def _comparison_signal_score(variant: dict[str, Any], common_end: float, usable_end: float) -> dict[str, Any]:
    points = [point for point in ((variant.get("timeline") or {}).get("points") or []) if isinstance(point, dict)]
    usable_points = [
        (float(point.get("seconds") or 0.0), max(0.0, min(100.0, float(point.get("signal_score") or 0.0))))
        for point in points
        if float(point.get("seconds") or 0.0) <= max(usable_end, 1.0)
    ]
    common_points = [(seconds, score) for seconds, score in usable_points if seconds <= common_end]
    if not common_points:
        common_points = usable_points
    if not common_points:
        fallback = int(round(float(variant.get("analysis_score") or variant.get("overall_score") or 0)))
        return {
            "comparison_score": fallback,
            "comparison_signal_avg": fallback,
            "comparison_early_avg": fallback,
            "comparison_floor": fallback,
            "comparison_window_seconds": round(common_end, 2),
        }

    scores = [score for _, score in common_points]
    early_limit = min(common_end, max(3.0, common_end * 0.45))
    early_scores = [score for seconds, score in common_points if seconds <= early_limit] or scores
    sorted_scores = sorted(scores)
    floor_count = max(1, int(round(len(sorted_scores) * 0.35)))
    floor_score = float(np.mean(sorted_scores[:floor_count]))
    signal_avg = float(np.mean(scores))
    early_avg = float(np.mean(early_scores))
    comparison_score = int(round(0.48 * early_avg + 0.34 * signal_avg + 0.18 * floor_score))
    return {
        "comparison_score": max(0, min(100, comparison_score)),
        "comparison_signal_avg": round(signal_avg, 1),
        "comparison_early_avg": round(early_avg, 1),
        "comparison_floor": round(floor_score, 1),
        "comparison_window_seconds": round(common_end, 2),
    }


def _build_speech_layer(
    duration_seconds: float,
    speech: SpeechRunResult | None,
    speech_error: str | None,
    profile: AnalysisModeProfile,
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

    metrics = [
        SpeechMetric("speech_start", "Старт речи", f"{first_start:.2f} c", _speech_start_summary(first_start)),
        SpeechMetric("speech_pace", "Слов в секунду", f"{pace:.2f}", _speech_pace_summary(pace)),
        SpeechMetric("articulation", "Насколько плотно сказано", f"{articulation:.2f}", _articulation_summary(articulation)),
        SpeechMetric("pause_ratio", "Доля пауз", f"{pause_ratio:.2f}", _pause_summary(pause_ratio)),
        SpeechMetric("confidence", "Уверенность ASR", f"{confidence:.2f}", _confidence_summary(confidence)),
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


def _read_video_info(video_path: str | Path) -> dict[str, Any]:
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


def _early_response_summary(score: int) -> str:
    return "Средняя активация в первой части ролика выше, чем в остальной. Для TRIBE это означает сильный ранний отклик." if score >= 75 else "Ранний отклик есть, но он не сильно превосходит остальную часть ролика." if score >= 60 else "Первая часть ролика даёт сравнительно слабый отклик относительно последующих сегментов."


def _sustain_summary(score: int) -> str:
    return "Уровень активации к концу ролика остаётся близким к началу. Сигнал не схлопывается." if score >= 75 else "Поздние сегменты ещё держат отклик, но уже слабее начальных." if score >= 60 else "Во второй половине средний отклик заметно ниже, чем в начале."


def _transition_summary(score: int) -> str:
    return "Сигнал часто меняется между соседними сегментами. Переходы плотные." if score >= 75 else "Переходы присутствуют, но их плотность умеренная." if score >= 60 else "Сигнал меняется редко или слишком неравномерно. Плотность переходов низкая."


def _stability_summary(score: int) -> str:
    return "Изменение сигнала выглядит относительно ровным, без сильной скачкообразности." if score >= 75 else "Сигнал в целом читается, но внутри есть заметная турбулентность." if score >= 60 else "Сигнал заметно шумный: соседние сегменты меняются слишком рвано."


def _density_summary(score: int) -> str:
    return "Средняя абсолютная активация высокая относительно собственных пиков ролика." if score >= 75 else "Плотность активации нормальная, но без выраженного запаса." if score >= 60 else "Средняя активация низкая относительно собственных пиков ролика."


def _speech_start_summary(start_seconds: float) -> str:
    return "Речь включается почти сразу. Текстовая опора приходит рано." if start_seconds <= 0.8 else "Речь стартует не мгновенно, но ещё в ранней фазе ролика." if start_seconds <= 2.0 else "Речь приходит поздно. До этого ролик держится в основном на визуале и звуке без слов."


def _speech_pace_summary(words_per_second: float) -> str:
    return "Речь подаётся плотно относительно длины ролика." if words_per_second >= 2.8 else "Темп речи умеренный, без сильной перегрузки текстом." if words_per_second >= 1.4 else "Речевой слой редкий: слов мало относительно общей длины ролика."


def _articulation_summary(words_per_second_active: float) -> str:
    return "Фразы произносятся плотно, без длинных растяжек внутри самой речи." if words_per_second_active >= 3.0 else "Артикуляция выглядит обычной по плотности." if words_per_second_active >= 1.8 else "Речь звучит растянуто или очень разреженно внутри речевых отрезков."


def _pause_summary(pause_ratio: float) -> str:
    return "Длинных пауз мало. Речевой поток собранный." if pause_ratio <= 0.12 else "Паузы есть, но они пока не доминируют в длительности ролика." if pause_ratio <= 0.28 else "Доля длинных пауз высокая. Между фразами много пустого воздуха."


def _confidence_summary(confidence: float) -> str:
    return "ASR уверенно распознаёт речь. Аудиодорожка читается чисто." if confidence >= 0.75 else "Речь в целом читается, но местами качество дорожки ограничивает уверенность распознавания." if confidence >= 0.55 else "Уверенность низкая: стоит проверить шум, громкость голоса и разборчивость дикции."


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


USER_METRIC_LABELS: dict[str, str] = {
    "early_response": "Старт графика",
    "sustain": "Как держится график",
    "transition": "Темп событий",
    "stability": "Резкие просадки",
    "density": "Средний уровень",
}


def _friendly_metric_label(key: str, fallback: str | None = None) -> str:
    return USER_METRIC_LABELS.get(str(key), fallback or str(key))


def _metric_label(key: str, profile: AnalysisModeProfile) -> str:
    del profile
    return _friendly_metric_label(key)


def _score_bucket(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 60:
        return "mid"
    return "low"


def _metric_summary(key: str, score: int, profile: AnalysisModeProfile) -> str:
    del profile
    library = {
        "early_response": {
            "high": "Ролик быстро набирает высокий уровень: главное видно рано и без долгого захода.",
            "mid": "Старт рабочий, но главное можно показать раньше или крупнее.",
            "low": "Начало набирает уровень поздно: зритель не сразу понимает, за что держаться.",
        },
        "sustain": {
            "high": "После старта линия держится ровно: в ролике регулярно появляется новый повод смотреть дальше.",
            "mid": "Линия держится не везде: часть отрезков можно сжать или оживить.",
            "low": "После сильных мест график быстро проседает: ролику не хватает новых событий по ходу просмотра.",
        },
        "transition": {
            "high": "Новые события появляются вовремя: кадр не застывает надолго.",
            "mid": "Темп в целом рабочий, но отдельные планы можно менять раньше.",
            "low": "Новых событий мало или они поздно появляются, поэтому некоторые участки начинают тянуться.",
        },
        "stability": {
            "high": "Резких провалов немного: зрителю легче непрерывно следить за главным.",
            "mid": "Есть заметные перепады: часть кадров слабее соседних и требует проверки.",
            "low": "Просадки резкие: рядом с сильными моментами есть участки, которые быстро теряют уровень.",
        },
        "density": {
            "high": "Средний уровень высокий: не только отдельные пики, но и большая часть ролика выглядит сильной.",
            "mid": "Средний уровень нормальный, но лучшие места заметно сильнее остальных.",
            "low": "Средний уровень низкий: ролик держится на отдельных удачных моментах, а не на всей конструкции.",
        },
    }
    return library.get(key, {}).get(_score_bucket(score), "")


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


def _signal_note(profile: AnalysisModeProfile) -> str:
    del profile
    return "Ниже показан расчетный график ролика: где уровень выше, где есть просадки и какие места стоит проверить в монтаже. Это подсказка для сравнительных тестов, а не обещание результата."


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


def _simple_metric_action(metric: ReviewMetric) -> str:
    actions = {
        "early_response": "Усиль старт: покажи главное раньше, убери длинный подвод и сделай первый кадр понятнее.",
        "sustain": "Подрежь участок перед просадкой или добавь там новый поворот, чтобы линия не падала после сильного момента.",
        "transition": "Добавь новое событие раньше: другой план, ракурс, действие, жест или короткую текстовую опору.",
        "stability": "Сглади резкую просадку: оставь один главный объект и убери детали, которые спорят за внимание.",
        "density": "Подними средний уровень: крупнее главный объект, чище фон, заметнее действие или сильнее контраст.",
    }
    return actions.get(metric.key, "Упрости этот участок и сделай главный объект заметнее.")


def _build_strengths(metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    del profile
    strengths = [
        f"Сильнее всего сейчас «{_metric_display(metrics[0])}»: {metrics[0].summary.lower()}",
        f"Второй рабочий ориентир - «{_metric_display(metrics[1])}»: {metrics[1].summary.lower()}",
    ]
    if speech_layer.get("available"):
        strengths.append("Речь распознана, поэтому сильные места можно сверить с конкретными фразами и подачей.")
    else:
        strengths.append("Без надежной речи сильные места лучше проверять по картинке, темпу и звуку.")
    return strengths


def _build_weaknesses(metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    del profile
    items = [
        f"Главное слабое место - «{_metric_display(metrics[-1])}»: {metrics[-1].summary.lower()}",
        f"Следом проверь «{_metric_display(metrics[-2])}»: там есть следующий понятный запас для правки.",
    ]
    if speech_layer.get("available") and isinstance(speech_layer.get("speech_start_seconds"), float) and speech_layer["speech_start_seconds"] > 2.0:
        items.append("Речь начинается поздно, поэтому первые секунды должны держаться на картинке и действии без словесной опоры.")
    return items


def _build_recommendations(metrics: list[ReviewMetric], drop_moments: list[dict[str, Any]], duration_seconds: float, speech: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    scores = _metric_scores(metrics)
    cutoff = 60 if profile.key == "simplified" else profile.recommendation_cutoff
    drops = _drop_timestamps(drop_moments)
    min_key = min(scores, key=scores.get)
    max_key = max(scores, key=scores.get)
    speech_start = speech.get("speech_start_seconds")
    speech_start_is_late = isinstance(speech_start, (int, float)) and float(speech_start) > 2.0
    speech_start_text = (
        f"Речь начинается около {float(speech_start):.2f} с. Если ключевой смысл в словах, перенеси главную фразу ближе к старту."
        if speech_start_is_late
        else ""
    )
    pause_ratio = speech.get("pause_ratio")
    pause_ratio_is_high = isinstance(pause_ratio, (int, float)) and float(pause_ratio) > 0.28

    candidates = [
        (scores.get("early_response", 0) < cutoff, "Старт набирает уровень поздно. Проверь первый кадр: главное должно появиться раньше, крупнее или с более ясным результатом."),
        (scores.get("sustain", 0) < cutoff, "После сильных мест график быстро падает. Перед просадкой добавь новый поворот, смену крупности или сократи отрезок, который не двигает сцену."),
        (scores.get("transition", 0) < cutoff, "Темп событий слабый: кадр слишком долго остается в одном состоянии. Добавь смену плана, жест, действие или короткий текст раньше."),
        (scores.get("stability", 0) < cutoff, "Есть резкие просадки. Сравни слабые окна с соседними сильными местами и убери лишние детали, которые размывают главный фокус."),
        (scores.get("density", 0) < cutoff, "Средний уровень ниже пиков. Подними базу ролика: крупнее главный объект, чище фон, заметнее движение или сильнее контраст."),
        (bool(drops), f"Сначала открой окна {drops}: там график проседает относительно соседних точек. Проверь, что в эти секунды меняется в кадре, тексте и темпе."),
        (bool(speech.get("available")) and speech_start_is_late, speech_start_text),
        (bool(speech.get("available")) and pause_ratio_is_high, "В речи много пустых промежутков. Подрежь паузы или сделай подачу плотнее, особенно рядом со слабыми окнами графика."),
        (not speech.get("available"), "Если слова важны для смысла, проверь громкость, шум и разборчивость: сейчас текстовый слой не дает надежной опоры для разбора."),
        (duration_seconds > 30, "После основной правки протестируй короткую версию. Так проще понять, выигрывает ли график от сокращения или теряется важный контекст."),
        (scores.get("early_response", 0) >= cutoff and scores.get("sustain", 0) < cutoff, "Начало уже можно оставить как ориентир, а правку начинать с середины: там нужно добавить новый информационный или визуальный повод смотреть дальше."),
        (scores.get("density", 0) >= 75 and scores.get("stability", 0) < cutoff, "Картинка в среднем сильная, но есть резкие провалы. Не усиливай все подряд - точечно сглади слабые окна, чтобы не потерять сильные кадры."),
        (scores.get("transition", 0) >= 75 and scores.get("sustain", 0) < cutoff, "Событий хватает, но линия все равно падает. Значит, проблема не только в частоте смен, а в том, насколько новые кадры дают понятный смысл."),
        (scores.get("early_response", 0) < cutoff and scores.get("density", 0) >= 70, "Визуал достаточно сильный, но старт не успевает его раскрыть. Перенеси самый понятный крупный кадр ближе к первым секундам."),
        (scores[min_key] < 45 and scores[max_key] >= 70, f"Разрыв между сильной и слабой стороной большой. Не перепридумывай весь ролик: сохрани «{_friendly_metric_label(max_key).lower()}» и отдельно чини «{_friendly_metric_label(min_key).lower()}»."),
    ]

    recs: list[str] = []
    for condition, text in candidates:
        if condition and text not in recs:
            recs.append(text)
        if len(recs) >= 6:
            break
    if not recs:
        recs.append("Явной крупной поломки по графику нет. Следующий тест лучше строить как A/B: меняй один элемент за раз и сравнивай старт, средний уровень и просадки.")
    return recs[:6]


def _build_simple_recommendations(metrics: list[ReviewMetric], drop_moments: list[dict[str, Any]], duration_seconds: float, speech: dict[str, Any]) -> list[str]:
    profile = get_analysis_mode_profile("simplified")
    return _build_recommendations(metrics, drop_moments, duration_seconds, speech, profile)


def _build_recommendation_plan(recommendations: list[str], top_metric: ReviewMetric, weak_metric: ReviewMetric, profile: AnalysisModeProfile) -> list[dict[str, str]]:
    del profile
    return [
        {"title": "Что оставить", "detail": f"Не ломай сильную часть «{_metric_display(top_metric)}»: она уже дает ролику рабочую опору."},
        {"title": "Что проверить первым", "detail": recommendations[0] if recommendations else _simple_metric_action(weak_metric)},
        {"title": "Как перепроверить", "detail": "После правки сравни старую и новую версии по графику: старт, средний уровень и резкие просадки должны стать лучше."},
    ]


def _build_verdict(overall_score: int, metrics: list[ReviewMetric], profile: AnalysisModeProfile) -> str:
    del profile
    scores = _metric_scores(metrics)
    strongest = _metric_display(metrics[0])
    weakest = _metric_display(metrics[-1])
    early = scores.get("early_response", 0)
    sustain = scores.get("sustain", 0)
    transition = scores.get("transition", 0)
    stability = scores.get("stability", 0)
    density = scores.get("density", 0)
    candidates = [
        (overall_score >= 78 and scores.get(metrics[-1].key, 0) >= 65, f"Ролик выглядит сильным и достаточно ровным. Главная опора - «{strongest}», а улучшать лучше точечно через «{weakest}»."),
        (overall_score >= 75 and scores.get(metrics[-1].key, 0) < 60, f"У ролика есть сильная основа, но она держится не везде. Оставь «{strongest}» и первым делом проверь «{weakest}»."),
        (early < 60 and density >= 65, "Главная проблема не в картинке, а в том, как быстро ролик раскрывает ее на старте. Сильный визуал стоит подать раньше."),
        (early < 60, f"Ролик слишком медленно набирает уровень. Первый приоритет - старт, затем уже правка «{weakest}»."),
        (sustain < 60 and early >= 65, "Начало работает лучше середины. Не ломай старт, а добавь новый поворот перед первым заметным провалом графика."),
        (transition < 60, "График проседает из-за нехватки новых событий. Участки без смены плана или действия нужно сжимать раньше."),
        (stability < 60, "Главный риск - резкие просадки. Ролик может иметь хорошие кадры, но слабые окна между ними тянут итог вниз."),
        (density < 60 and overall_score < 55, "Пока ролик держится на отдельных моментах. Нужно поднимать средний уровень, а не только искать один яркий пик."),
        (overall_score >= 60, f"Версия рабочая, но неровная. Сильнее всего выглядит «{strongest}», главный запас - «{weakest}»."),
        (overall_score < 60, f"Это скорее черновик для доработки. Сначала усили «{weakest}», потом перепроверь весь ролик сравнительным тестом."),
    ]
    return _pick_template(candidates, f"Главный ориентир - «{strongest}». Основная правка сейчас в зоне «{weakest}».")


def _build_executive_summary(overall_score: int, top_metric: ReviewMetric, weak_metric: ReviewMetric, runner_metric: ReviewMetric, speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> str:
    del profile
    scores = {top_metric.key: top_metric.score, weak_metric.key: weak_metric.score, runner_metric.key: runner_metric.score}
    top = _metric_display(top_metric)
    runner = _metric_display(runner_metric)
    weak = _metric_display(weak_metric)
    speech = _speech_line(speech_layer)
    candidates = [
        (overall_score >= 80, f"Это сильная версия: график держится высоко, а «{top}» дает основную опору. Улучшения стоит делать точечно через «{weak}». {speech}"),
        (overall_score >= 72 and weak_metric.score < 60, f"Общий уровень хороший, но итог ограничивает «{weak}». Сначала проверь слабые окна, не меняя то, что уже работает в «{top}». {speech}"),
        (weak_metric.key == "early_response", f"Главный вопрос - старт: ролик поздно набирает уровень. Сохрани «{top}», но перенеси более понятный кадр или смысл ближе к первым секундам. {speech}"),
        (weak_metric.key == "sustain", f"Старт и отдельные кадры работают лучше, чем продолжение. Нужно понять, где график начинает падать, и дать там новый поворот. {speech}"),
        (weak_metric.key == "transition", f"Ролику не хватает новых событий в нужный момент. «{top}» можно сохранить, а монтаж проверить на слишком длинные планы. {speech}"),
        (weak_metric.key == "stability", f"Главная проблема - резкие просадки между сильными местами. Проверь слабые окна на лишние детали, паузы или потерю фокуса. {speech}"),
        (weak_metric.key == "density", f"Лучшие места заметно сильнее среднего уровня. Нужно не добавлять еще один пик, а поднять базовую силу большинства кадров. {speech}"),
        (scores.get(top_metric.key, 0) - scores.get(weak_metric.key, 0) >= 25, f"Разрыв между сильной и слабой частью большой: «{top}» трогать опасно, а «{weak}» дает самый понятный запас роста. {speech}"),
        (overall_score >= 60, f"Версия уже рабочая, но требует аккуратной правки. Ориентир - «{top}», второй сильный признак - «{runner}», главный ремонт - «{weak}». {speech}"),
        (overall_score < 60, f"Пока это внутренний вариант для доработки. Начни не с полной переработки, а с одного слабого признака: «{weak}». {speech}"),
    ]
    return _pick_template(candidates, f"Сильная сторона - «{top}», слабая - «{weak}». Следующий шаг: одна правка и повторное сравнение графика.")


def _build_product_summary(overall_score: int, ordered_metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> str:
    del profile
    scores = _metric_scores(ordered_metrics)
    strongest = _metric_display(ordered_metrics[0])
    weakest = _metric_display(ordered_metrics[-1])
    speech = _speech_line(speech_layer)
    candidates = [
        (overall_score >= 80, f"Можно брать эту версию как базу для следующего теста. Она уже держит график достаточно высоко; правки лучше ограничить зоной «{weakest}». {speech}"),
        (overall_score >= 70 and scores.get("early_response", 0) >= 70, f"Старт можно сохранять как рабочий. Следующий тест лучше строить вокруг того, как ролик держится после первых секунд. {speech}"),
        (scores.get("early_response", 0) < 60, f"Для продукта сейчас важнее всего быстрее объяснить ценность. Перенеси результат, товар или конфликт ближе к началу. {speech}"),
        (scores.get("sustain", 0) < 60, f"Версия теряет темп после удачных моментов. Добавь в середину новый смысловой шаг: действие, реакцию, деталь или payoff. {speech}"),
        (scores.get("transition", 0) < 60, f"Монтаж выглядит затянутым. Следующий вариант должен чаще менять состояние кадра, но без хаотичной нарезки. {speech}"),
        (scores.get("stability", 0) < 60, f"Слабые места похожи на потерю фокуса. Для следующей версии сделай главный объект и действие проще для чтения. {speech}"),
        (scores.get("density", 0) < 60, f"Ролику не хватает среднего уровня: отдельные хорошие места есть, но базовая картинка должна стать сильнее. {speech}"),
        (overall_score >= 60, f"Основа рабочая. Не перепридумывай весь ролик: сохрани «{strongest}» и проверь одну правку в зоне «{weakest}». {speech}"),
        (overall_score < 50, f"Сейчас лучше делать не мелкий полишинг, а новую итерацию вокруг слабого признака «{weakest}». {speech}"),
        (True, f"Для следующего прогона меняй один элемент за раз и смотри, что происходит со стартом, средним уровнем и просадками. {speech}"),
    ]
    return _pick_template(candidates, f"Сильнее всего выглядит «{strongest}», слабее всего - «{weakest}».")


def _comparison_value(variant: dict[str, Any], key: str, fallback: float = 0.0) -> float:
    value = variant.get(key)
    if value is None:
        value = variant.get("overall_score", fallback)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _comparison_score_value(variant: dict[str, Any]) -> int:
    return int(round(_comparison_value(variant, "comparison_score", _comparison_value(variant, "overall_score", 0.0))))


def _variant_metric(variant: dict[str, Any], mode: str) -> dict[str, Any]:
    metrics = [metric for metric in variant.get("metrics", []) if isinstance(metric, dict)]
    if not metrics:
        return {"key": "sustain", "label": _friendly_metric_label("sustain"), "score": 0}
    fn = max if mode == "max" else min
    metric = fn(metrics, key=lambda item: int(item.get("score") or 0))
    return {
        "key": str(metric.get("key") or ""),
        "label": _friendly_metric_label(str(metric.get("key") or ""), str(metric.get("label") or "")),
        "score": int(metric.get("score") or 0),
    }


def _build_comparison_rows(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metric_keys = [str(metric.get("key") or "") for metric in variants[0].get("metrics", []) if isinstance(metric, dict)]
    rows = []
    for key in metric_keys:
        scores = [{"variant_key": variant["variant_key"], "name": variant["title"], "score": int(variant["metric_lookup"].get(key, 0))} for variant in variants]
        ordered = sorted(scores, key=lambda item: item["score"], reverse=True)
        rows.append({
            "key": key,
            "label": _friendly_metric_label(key),
            "winner_name": ordered[0]["name"],
            "winner_score": ordered[0]["score"],
            "spread": ordered[0]["score"] - ordered[-1]["score"],
            "scores": scores,
        })
    rows.sort(key=lambda item: item["spread"], reverse=True)
    return rows


def _build_axis_winners(comparison_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": row["label"],
            "winner_name": row["winner_name"],
            "winner_score": row["winner_score"],
            "summary": f"По показателю «{row['label'].lower()}» у этой версии самый заметный отрыв от остальных.",
        }
        for row in comparison_rows[:4]
    ]


def _build_common_gaps(variants: list[dict[str, Any]], profile: AnalysisModeProfile) -> list[str]:
    gaps = []
    metric_keys = [str(metric.get("key") or "") for metric in variants[0].get("metrics", []) if isinstance(metric, dict)]
    for key in metric_keys:
        scores = [int(variant["metric_lookup"].get(key, 0)) for variant in variants]
        if scores and mean(scores) < profile.recommendation_cutoff:
            gaps.append(f"Во всех версиях слабее выглядит «{_friendly_metric_label(key).lower()}». Даже лидер не дает там уверенного запаса, поэтому это хороший кандидат для отдельного теста.")
    return gaps[:3]


def _build_ranking(variants: list[dict[str, Any]], best: dict[str, Any]) -> list[dict[str, Any]]:
    ranking = []
    best_score = _comparison_score_value(best)
    for index, variant in enumerate(variants, start=1):
        strongest = _variant_metric(variant, "max")
        weakest = _variant_metric(variant, "min")
        score = _comparison_score_value(variant)
        delta = best_score - score
        ranking.append({
            "rank": index,
            "variant_key": variant["variant_key"],
            "name": variant["title"],
            "overall_score": score,
            "analysis_score": variant.get("analysis_score"),
            "comparison_signal_avg": variant.get("comparison_signal_avg"),
            "comparison_early_avg": variant.get("comparison_early_avg"),
            "comparison_window_seconds": variant.get("comparison_window_seconds"),
            "delta_vs_best": delta,
            "strongest": strongest["label"],
            "weakest": weakest["label"],
            "summary": _variant_compare_summary(variant, delta),
        })
    return ranking


def _variant_compare_summary(variant: dict[str, Any], delta: int) -> str:
    strongest = _variant_metric(variant, "max")
    weakest = _variant_metric(variant, "min")
    avg = _comparison_value(variant, "comparison_signal_avg", _comparison_value(variant, "overall_score", 0.0))
    early = _comparison_value(variant, "comparison_early_avg", avg)
    floor = _comparison_value(variant, "comparison_floor", avg)
    score = _comparison_score_value(variant)
    candidates = [
        (delta == 0 and early >= 65 and avg >= 60, f"Лидер сравнения: быстро набирает уровень и держит хороший средний график. Главная опора - «{strongest['label'].lower()}»."),
        (delta == 0 and floor < 35, f"Лидер по итоговому score, но не без риска: есть глубокие просадки. Следующая правка - «{weakest['label'].lower()}»."),
        (delta == 0, f"Лидер сравнения. Версия выигрывает не одним всплеском, а суммой показателей; сильнее всего выглядит «{strongest['label'].lower()}»."),
        (delta <= 3 and early >= avg + 8, f"Почти лидер за счет сильного старта, но дальше средний уровень не добирает. Проверь «{weakest['label'].lower()}»."),
        (delta <= 3, f"Почти рядом с лидером: разница небольшая. В следующем тесте сравни именно старт и середину, а не отдельные пики."),
        (delta <= 7 and avg >= 55, f"Версия конкурентная по среднему уровню, но уступает лидеру в деталях. Главный резерв - «{weakest['label'].lower()}»."),
        (early < 45, "Версия проигрывает старт: график поздно набирает уровень, поэтому даже сильные моменты дальше не спасают итог полностью."),
        (floor < 30, f"Основная проблема - глубокие провалы. Сильная сторона «{strongest['label'].lower()}» есть, но «{weakest['label'].lower()}» тянет результат вниз."),
        (score >= 55, f"У версии есть рабочая база, но лидер выглядит ровнее. Сохрани «{strongest['label'].lower()}» и отдельно проверь «{weakest['label'].lower()}»."),
        (True, f"Версия заметно уступает лидеру. Лучшее в ней - «{strongest['label'].lower()}», но общий график пока слишком неровный."),
    ]
    return _pick_template(candidates, "")


def _build_compare_verdict(best: dict[str, Any], runner_up: dict[str, Any], variant_count: int) -> str:
    delta = _comparison_score_value(best) - _comparison_score_value(runner_up)
    best_avg = _comparison_value(best, "comparison_signal_avg", _comparison_score_value(best))
    best_early = _comparison_value(best, "comparison_early_avg", best_avg)
    runner_avg = _comparison_value(runner_up, "comparison_signal_avg", _comparison_score_value(runner_up))
    window = best.get("comparison_window_seconds")
    window_line = f" Сравнение идет по общему окну примерно до {window} с; последние 5 секунд не участвуют." if window else ""
    candidates = [
        (delta >= 12 and best_early >= 65, f"Из {variant_count} версий явнее всего лидирует «{best['title']}»: она быстро набирает график и сохраняет отрыв по среднему уровню.{window_line}"),
        (delta >= 12, f"«{best['title']}» сейчас заметно впереди по общему score сравнения. Главная причина - более высокий средний уровень, а не один случайный пик.{window_line}"),
        (delta >= 7 and runner_avg >= best_avg - 5, f"«{best['title']}» лидирует, но «{runner_up['title']}» остается близким контролем. Разницу лучше перепроверить новым A/B, особенно в начале и середине.{window_line}"),
        (delta >= 7, f"«{best['title']}» выглядит первым кандидатом для следующего теста: у нее сильнее рабочая часть графика и меньше цена слабых окон.{window_line}"),
        (delta <= 3 and best_early < runner_avg, f"Лидерство «{best['title']}» минимальное. Это не окончательный победитель, а версия, которую стоит проверить против «{runner_up['title']}» еще раз.{window_line}"),
        (delta <= 3, f"Разрыв между «{best['title']}» и «{runner_up['title']}» небольшой. Решение лучше принимать после следующего сравнительного прогона с одной точечной правкой.{window_line}"),
        (best_early >= 70 and best_avg < 55, f"«{best['title']}» выигрывает за счет сильного старта, но средний уровень пока не дает большого запаса. Нужна проверка середины ролика.{window_line}"),
        (best_avg >= 65, f"«{best['title']}» лидирует за счет более высокого среднего уровня графика. Это надежнее, чем победа за счет одного позднего всплеска.{window_line}"),
        (best_avg < 50, f"Даже лидер «{best['title']}» пока не выглядит уверенным. Сравнение показывает лучший из текущих вариантов, но не финальную версию.{window_line}"),
        (True, f"Сейчас первым стоит брать «{best['title']}», а «{runner_up['title']}» оставить ближайшим контролем для следующего A/B.{window_line}"),
    ]
    return _pick_template(candidates, "")


def _build_compare_executive_summary(best: dict[str, Any], runner_up: dict[str, Any], axis_winners: list[dict[str, Any]], profile: AnalysisModeProfile) -> str:
    del profile
    best_score = _comparison_score_value(best)
    runner_score = _comparison_score_value(runner_up)
    delta = best_score - runner_score
    best_avg = round(_comparison_value(best, "comparison_signal_avg", best_score), 1)
    best_early = round(_comparison_value(best, "comparison_early_avg", best_score), 1)
    runner_avg = round(_comparison_value(runner_up, "comparison_signal_avg", runner_score), 1)
    top_axis = str(axis_winners[0]["label"]).lower() if axis_winners else _variant_metric(best, "max")["label"].lower()
    candidates = [
        (delta >= 12 and best_early >= 65, f"Лучший кандидат - «{best['title']}»: старт {best_early}, средний уровень {best_avg}. Отрыв от «{runner_up['title']}» - {delta} пунктов, поэтому ее логично брать базой."),
        (delta >= 12, f"«{best['title']}» впереди на {delta} пунктов. Важнее всего не пик, а средний уровень {best_avg} против {runner_avg} у ближайшей версии."),
        (delta <= 3, f"«{best['title']}» пока впереди всего на {delta} пункта. Это близкая гонка: «{runner_up['title']}» стоит оставить в контроле и сравнить еще раз после точечной правки."),
        (best_early < 50, f"Лидер выбран по сумме графика, но старт у него не идеален: {best_early}. Следующий тест должен усилить первые секунды, а не только середину."),
        (best_avg < 50, f"Даже лучшая версия пока не дает высокого среднего уровня. «{best['title']}» выигрывает текущий набор, но весь пакет нуждается в усилении."),
        (top_axis == "старт графика", f"Разница лучше всего видна в старте: «{best['title']}» быстрее набирает график и за счет этого обходит «{runner_up['title']}»."),
        (top_axis == "средний уровень", f"Ключевой плюс лидера - средний уровень. «{best['title']}» выглядит полезнее как база, потому что держится не только на отдельных всплесках."),
        (top_axis == "резкие просадки", f"Лидер выигрывает тем, что меньше проваливается между сильными местами. Для следующей версии важно сохранить эту ровность."),
        (top_axis == "темп событий", f"Главное отличие лидера - темп событий. Он чаще дает зрителю новый повод смотреть дальше."),
        (True, f"«{best['title']}» сейчас первый кандидат, «{runner_up['title']}» - контроль. Сравнивайте старт, средний уровень и просадки, а не только самый высокий пик."),
    ]
    return _pick_template(candidates, "")


def _build_compare_product_summary(best: dict[str, Any], runner_up: dict[str, Any], common_gaps: list[str], profile: AnalysisModeProfile) -> str:
    del profile
    delta = _comparison_score_value(best) - _comparison_score_value(runner_up)
    best_avg = _comparison_value(best, "comparison_signal_avg", _comparison_score_value(best))
    best_floor = _comparison_value(best, "comparison_floor", best_avg)
    weakest = _variant_metric(best, "min")["label"].lower()
    gap_line = common_gaps[0] if common_gaps else ""
    candidates = [
        (delta >= 10 and best_floor >= 45, f"Для следующего теста бери «{best['title']}» как основную версию: она выигрывает не только пиком, но и более устойчивым графиком без глубоких провалов."),
        (delta >= 10, f"«{best['title']}» лучше текущего набора, но слабые окна все еще есть. Перед масштабированием отдельно проверь «{weakest}»."),
        (delta <= 3, f"Не называй победителя финальным. «{best['title']}» и «{runner_up['title']}» близко, поэтому следующий тест должен менять один конкретный элемент."),
        (best_avg < 50, f"Даже лидер пока слабоват по среднему уровню. Нужно не выбирать победителя, а поднять базовую силу всех версий."),
        (bool(gap_line), f"Первой базой бери «{best['title']}», но общий риск одинаков для всех: {gap_line}"),
        (_variant_metric(runner_up, "max")["key"] == _variant_metric(best, "min")["key"], f"У «{runner_up['title']}» есть полезная подсказка по слабому месту лидера. Сравни, как она решает «{weakest}», и перенеси прием в «{best['title']}»."),
        (_comparison_value(best, "comparison_early_avg", 0) < 55, f"Лидерство есть, но старт можно усилить. Следующая итерация «{best['title']}» должна быстрее показывать главный объект или результат."),
        (_comparison_value(best, "comparison_floor", 0) < 35, f"Главная задача - убрать глубокие провалы у лидера. Не добавляй новые эффекты, пока слабые окна не станут понятнее."),
        (delta >= 5, f"«{best['title']}» можно нести первой, а «{runner_up['title']}» оставить контрольной версией для проверки следующей правки."),
        (True, f"Следующий шаг - A/B между «{best['title']}» и «{runner_up['title']}». Смотрите, какая версия лучше держит старт, середину и слабые окна."),
    ]
    return _pick_template(candidates, "")


def _build_comparison_recommendations(best: dict[str, Any], runner_up: dict[str, Any], common_gaps: list[str]) -> list[str]:
    delta = _comparison_score_value(best) - _comparison_score_value(runner_up)
    best_avg = _comparison_value(best, "comparison_signal_avg", _comparison_score_value(best))
    best_early = _comparison_value(best, "comparison_early_avg", best_avg)
    best_floor = _comparison_value(best, "comparison_floor", best_avg)
    runner_avg = _comparison_value(runner_up, "comparison_signal_avg", _comparison_score_value(runner_up))
    weakest = _variant_metric(best, "min")["label"].lower()
    strongest = _variant_metric(best, "max")["label"].lower()
    candidates = [
        (True, f"В следующий тест неси «{best['title']}» как базу: сейчас у нее лучший score по общему окну сравнения."),
        (delta <= 3, f"Отрыв маленький. Не делай вывод по одному прогону: сравни «{best['title']}» и «{runner_up['title']}» еще раз после одной точечной правки."),
        (delta >= 8, f"Сохрани у лидера «{strongest}» без лишних изменений. Это главный прием, который сейчас дает отрыв."),
        (best_early < 55, "У лидера есть запас в первых секундах. Попробуй раньше показать главный объект, результат или конфликт."),
        (best_avg < 55, "Средний уровень у лидера недостаточно высокий. Нужна правка не одного пика, а нескольких обычных кадров между сильными моментами."),
        (best_floor < 35, f"У лидера есть глубокие просадки. Начни с «{weakest}» и сравни слабые окна с соседними сильными местами."),
        (runner_avg >= best_avg - 5, f"«{runner_up['title']}» оставь ближайшим контролем: по среднему уровню она близко и может подсказать, что именно переносить в лидера."),
        (bool(common_gaps), common_gaps[0] if common_gaps else ""),
        (_comparison_value(runner_up, "comparison_early_avg", 0) > best_early + 5, f"У «{runner_up['title']}» старт лучше, чем у лидера. Проверь, можно ли перенести ее первый кадр или заход в «{best['title']}»."),
        (True, "Последние 5 секунд не используй как главный аргумент. Смотри старт, середину и провалы в общем окне сравнения."),
    ]
    recs: list[str] = []
    for condition, text in candidates:
        if condition and text and text not in recs:
            recs.append(text)
        if len(recs) >= 4:
            break
    return recs[:4]


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


# Follow-up F3: ACTION_VARIANTS lives in report_localization.py now (the
# ru/en pair sits with the rest of the translation tables). We re-export
# the Russian dict under its historical name so callers (notably
# `_action_copy_for_metric` below and `tribe_review.copy_ru`) keep working.
from report_localization import ACTION_VARIANTS_RU as ACTION_VARIANTS  # noqa: E402


def _action_copy_for_metric(metric_key: str, variant_index: int) -> tuple[str, str]:
    variants = ACTION_VARIANTS.get(metric_key) or ACTION_VARIANTS["sustain"]
    return variants[variant_index % len(variants)]


def _action_metric_candidates(metrics: list[Any], speech_layer: dict[str, Any]) -> list[str]:
    keys = [str(item.key) for item in sorted(metrics, key=lambda metric: metric.score) if getattr(item, "key", "")]
    if speech_layer.get("available") and isinstance(speech_layer.get("speech_start_seconds"), float) and speech_layer["speech_start_seconds"] > 2.0:
        keys.append("speech_start")
    if speech_layer.get("available") and isinstance(speech_layer.get("pause_ratio"), float) and speech_layer["pause_ratio"] > 0.28:
        keys.append("pause")

    seen: set[str] = set()
    ordered: list[str] = []
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered or ["sustain"]


def _build_action_items(
    recommendations: list[str],
    focus_windows: list[Any],
    drop_moments: list[dict[str, Any]],
    speech_layer: dict[str, Any],
    metrics: list[Any],
    profile: Any,
) -> list[dict[str, str]]:
    del recommendations

    targets: list[dict[str, str]] = []
    for item in drop_moments:
        timestamp = str(item.get("timestamp") or "").strip()
        if not timestamp:
            continue
        targets.append(
            {
                "timestamp": timestamp,
                "why": str(item.get("reason") or "").strip(),
            }
        )

    if not targets and focus_windows:
        weak_window = focus_windows[1] if getattr(profile, "key", "") == "simplified" and len(focus_windows) > 1 else focus_windows[0]
        if getattr(profile, "key", "") != "simplified":
            weak_window = next(
                (
                    item
                    for item in focus_windows
                    if "лаб" in str(getattr(item, "label", "")).lower()
                ),
                focus_windows[0],
            )
        targets.append(
            {
                "timestamp": str(getattr(weak_window, "timestamp", "")).strip(),
                "why": str(getattr(weak_window, "summary", "")).strip(),
            }
        )

    metric_keys = _action_metric_candidates(metrics, speech_layer)
    actions: list[dict[str, str]] = []
    used_titles: set[str] = set()
    metric_use_count: dict[str, int] = {}
    for index, target in enumerate(targets[: getattr(profile, "max_action_items", 4)]):
        metric_key = metric_keys[min(index, len(metric_keys) - 1)]
        variant_index = metric_use_count.get(metric_key, 0)
        title, instruction = _action_copy_for_metric(metric_key, variant_index)
        metric_use_count[metric_key] = variant_index + 1
        if title in used_titles:
            for offset in range(1, 5):
                title, instruction = _action_copy_for_metric(metric_key, variant_index + offset)
                if title not in used_titles:
                    break
        used_titles.add(title)
        actions.append(
            {
                "timestamp": target["timestamp"],
                "title": title,
                "instruction": instruction,
                "why": target["why"],
            }
        )

    seen_timestamps: set[str] = set()
    deduped: list[dict[str, str]] = []
    for action in actions:
        timestamp = action["timestamp"]
        if not timestamp or timestamp in seen_timestamps:
            continue
        seen_timestamps.add(timestamp)
        deduped.append(action)
    return deduped[: getattr(profile, "max_action_items", 4)]
