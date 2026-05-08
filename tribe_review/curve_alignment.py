"""Editorial-layer alignment helpers for the official TRIBE curve.

Extracted from ``app.py`` (Follow-up F2). These functions reshape the local
recommendation layer so that focus windows, drop moments, action items and
seek targets follow the *official* TRIBE response curve instead of the
editorial layer's own picks. They are imported back into ``app.py`` by
``_seed_editorial_curve_points`` and ``_sync_editorial_to_official_curve``.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

import numpy as np


def _extract_official_curve_points(
    official_result: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    timeline = official_result.get("timeline") if isinstance(official_result.get("timeline"), dict) else {}
    points = [item for item in timeline.get("points", []) if isinstance(item, dict)]
    if not points:
        return None, []

    timestamps = np.asarray([float(item.get("seconds") or 0.0) for item in points], dtype=float)
    scores = np.asarray([float(item.get("signal_score") or 0.0) for item in points], dtype=float)
    if not len(timestamps) or not len(scores):
        return None, []

    video = official_result.get("video") if isinstance(official_result.get("video"), dict) else {}
    duration = float(video.get("duration_seconds") or (timestamps[-1] if len(timestamps) else 0.0))
    start_cutoff = 3.0 if duration > 8.0 else min(1.0, max(0.35, duration * 0.12))
    tail_buffer = 5.0 if duration > 8.0 else max(1.0, duration * 0.30)
    edit_cutoff = duration - tail_buffer if duration > 0 else (timestamps[-1] if len(timestamps) else 0.0)
    valid_edit_indices = [
        index
        for index, second in enumerate(timestamps)
        if start_cutoff < second < edit_cutoff
    ]
    if not valid_edit_indices:
        valid_edit_indices = list(range(len(timestamps)))

    strong_windows = _pick_curve_windows(timestamps, scores, prefer="high", count=2, allowed_indices=valid_edit_indices)
    if not strong_windows:
        strong_windows = _pick_curve_windows(timestamps, scores, prefer="high", count=2)
    weak_windows = _pick_curve_windows(timestamps, scores, prefer="low", count=4, allowed_indices=valid_edit_indices)
    weak_windows = _filter_meaningful_curve_dips(scores, weak_windows, valid_edit_indices)
    reference_point = _curve_point_from_window(timestamps, scores, strong_windows[0]) if strong_windows else None
    dip_points = [_curve_point_from_window(timestamps, scores, item) for item in weak_windows]
    if reference_point:
        dip_points = [item for item in dip_points if item["center_index"] != reference_point["center_index"]]
    return reference_point, dip_points


def _filter_meaningful_curve_dips(
    scores: np.ndarray,
    weak_windows: list[dict[str, Any]],
    valid_indices: list[int],
) -> list[dict[str, Any]]:
    if not weak_windows or not len(scores):
        return []

    valid_scores = scores[valid_indices] if valid_indices else scores
    if not len(valid_scores):
        valid_scores = scores
    working_mean = float(np.mean(valid_scores))
    working_max = float(np.max(valid_scores))

    meaningful: list[dict[str, Any]] = []
    for window in weak_windows:
        center = int(window.get("center_index") or 0)
        score = float(window.get("score") or scores[center])
        local_start = max(0, center - 2)
        local_end = min(len(scores), center + 3)
        local_peak = float(np.max(scores[local_start:local_end])) if local_end > local_start else score

        is_low_absolute = score <= 55.0
        is_local_drop = score <= 65.0 and (local_peak - score) >= 12.0
        is_weak_for_this_cut = score <= (working_mean - 15.0) and (working_max - score) >= 20.0
        if is_low_absolute or is_local_drop or is_weak_for_this_cut:
            meaningful.append(window)

    return meaningful


def _pick_curve_windows(
    timestamps: np.ndarray,
    scores: np.ndarray,
    prefer: str,
    count: int,
    allowed_indices: list[int] | None = None,
) -> list[dict[str, Any]]:
    if not len(scores):
        return []

    allowed = set(allowed_indices) if allowed_indices is not None else set(range(len(scores)))
    centers = sorted(allowed) if allowed else list(range(len(scores)))
    if not centers:
        return []

    window_size = max(3, min(8, len(scores) // 8 or 3))
    scored_windows: list[tuple[float, int, int, int]] = []
    for center in centers:
        half = window_size // 2
        raw_start = max(0, center - half)
        raw_end = min(len(scores) - 1, center + half)
        covered = [index for index in range(raw_start, raw_end + 1) if index in allowed]
        if not covered:
            continue
        start_index = covered[0]
        end_index = covered[-1]
        score = float(np.mean(scores[covered]))
        scored_windows.append((score, center, start_index, end_index))

    scored_windows.sort(key=lambda item: item[0], reverse=(prefer == "high"))
    selected: list[dict[str, Any]] = []
    for score, center, start_index, end_index in scored_windows:
        overlaps = any(abs(center - int(item["center_index"])) <= window_size for item in selected)
        if overlaps:
            continue
        selected.append(
            {
                "score": round(score, 1),
                "center_index": int(center),
                "start_index": int(start_index),
                "end_index": int(end_index),
            }
        )
        if len(selected) >= count:
            break
    return selected


def _curve_point_from_window(
    timestamps: np.ndarray,
    scores: np.ndarray,
    window: dict[str, Any],
) -> dict[str, Any]:
    center_index = int(window["center_index"])
    seconds = round(float(timestamps[center_index]), 2)
    return {
        "seconds": seconds,
        "timestamp": _format_editorial_timestamp(seconds),
        "score": round(float(window.get("score") or scores[center_index]), 1),
        "center_index": center_index,
        "start_seconds": round(float(timestamps[int(window["start_index"])]), 2),
        "end_seconds": round(float(timestamps[int(window["end_index"])]), 2),
    }


def _build_curve_focus_windows(
    reference_point: dict[str, Any] | None,
    dip_points: list[dict[str, Any]],
    existing_windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seeds = [point for point in [reference_point, *dip_points[:2]] if point]
    if not seeds:
        return existing_windows

    default_labels = ("Лучший кусок", "Где чинить первым", "Еще одна просадка")
    default_summaries = (
        "Используй этот участок как ориентир.",
        "На графике здесь виден заметный спад.",
        "Здесь на графике есть еще один заметный спад.",
    )
    rewritten: list[dict[str, Any]] = []
    for index, point in enumerate(seeds):
        template = existing_windows[index] if index < len(existing_windows) else {}
        rewritten.append(
            {
                "label": str(template.get("label") or default_labels[index]),
                "timestamp": point["timestamp"],
                "seconds": point["seconds"],
                "summary": str(template.get("summary") or default_summaries[index]),
            }
        )
    return rewritten


def _build_curve_drop_moments(
    dip_points: list[dict[str, Any]],
    existing_drops: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rewritten: list[dict[str, Any]] = []
    for index, point in enumerate(dip_points[:4]):
        template = existing_drops[index] if index < len(existing_drops) else {}
        rewritten.append(
            {
                "seconds": point["seconds"],
                "timestamp": point["timestamp"],
                "reason": str(template.get("reason") or "На графике здесь виден заметный спад."),
            }
        )
    return rewritten


def _rebase_action_items_to_curve(
    review: dict[str, Any],
    reference_point: dict[str, Any] | None,
    dip_points: list[dict[str, Any]],
) -> None:
    actions = [deepcopy(item) for item in review.get("action_items", []) if isinstance(item, dict)]
    if not actions:
        return

    dip_timestamps = [str(item["timestamp"]) for item in dip_points if item.get("timestamp")]
    reference_ts = str(reference_point["timestamp"]) if reference_point and reference_point.get("timestamp") else ""
    updated: list[dict[str, Any]] = []
    dip_index = 0

    for item in actions:
        title = str(item.get("title") or "").strip().lower()
        is_keep = title in {"оставить как есть", "keep as is"}
        if is_keep:
            if reference_ts:
                item["timestamp"] = reference_ts
            updated.append(item)
            continue
        if dip_index >= len(dip_timestamps):
            continue
        item["timestamp"] = dip_timestamps[dip_index]
        dip_index += 1
        updated.append(item)

    review["action_items"] = updated[:4]


def _rebuild_editorial_lists(review: dict[str, Any]) -> None:
    actions = [item for item in review.get("action_items", []) if isinstance(item, dict)]
    if not actions:
        return

    keep_item = next((item for item in actions if _is_keep_action(item)), None)
    edit_items = [item for item in actions if not _is_keep_action(item)]

    existing_strengths = [item for item in review.get("strengths", []) if isinstance(item, str) and item.strip()]
    strengths: list[str] = []
    if keep_item:
        strengths.append(_timed_instruction_line(keep_item))
    extra_strength = next((item for item in existing_strengths if not _looks_timed_line(item)), "")
    if extra_strength:
        strengths.append(extra_strength)
    if strengths:
        review["strengths"] = strengths[:2]

    if edit_items:
        review["weaknesses"] = [_timed_instruction_line(item) for item in edit_items[:2]]

    plan: list[dict[str, str]] = []
    if keep_item:
        plan.append(
            {
                "title": "Оставить",
                "detail": _timed_instruction_line(keep_item),
            }
        )
    if edit_items:
        plan.append(
            {
                "title": "Сделать первым",
                "detail": _timed_instruction_line(edit_items[0]),
            }
        )
    if len(edit_items) > 1:
        plan.append(
            {
                "title": "Сделать потом",
                "detail": _timed_instruction_line(edit_items[1]),
            }
        )
    if plan:
        review["recommendation_plan"] = plan[:3]


def _build_editorial_seek_targets(review: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for item in review.get("focus_windows", []):
        if isinstance(item, dict):
            targets.append(
                {
                    "label": str(item.get("label") or ""),
                    "timestamp": str(item.get("timestamp") or ""),
                    "seconds": item.get("seconds"),
                    "kind": "focus",
                    "summary": str(item.get("summary") or ""),
                }
            )
    for item in review.get("drop_moments", []):
        if isinstance(item, dict):
            targets.append(
                {
                    "label": "Подозрительный момент",
                    "timestamp": str(item.get("timestamp") or ""),
                    "seconds": item.get("seconds"),
                    "kind": "drop",
                    "summary": str(item.get("reason") or ""),
                }
            )
    speech = review.get("speech")
    if isinstance(speech, dict):
        for segment in speech.get("segments", [])[:6]:
            if not isinstance(segment, dict):
                continue
            start = segment.get("start")
            if not isinstance(start, (int, float)):
                continue
            targets.append(
                {
                    "label": "Speech segment",
                    "timestamp": _format_editorial_timestamp(float(start)),
                    "seconds": round(float(start), 2),
                    "kind": "speech",
                    "summary": str(segment.get("text") or ""),
                }
            )
    return targets


def _is_keep_action(item: dict[str, Any]) -> bool:
    title = str(item.get("title") or "").strip().lower()
    return (
        title in {"оставить как есть", "keep as is"}
        or "сохран" in title
        or "keep" in title
    )


def _timed_instruction_line(item: dict[str, Any]) -> str:
    timestamp = str(item.get("timestamp") or "").strip()
    instruction = _compact_editorial_text(str(item.get("instruction") or ""))
    return f"{timestamp}: {instruction}" if timestamp else instruction


def _compact_editorial_text(text: str) -> str:
    cleaned = " ".join(str(text).split()).strip(" -,:.")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else ""


def _looks_timed_line(text: str) -> bool:
    return bool(re.match(r"^\d{2}:\d{2}(?:\s*-\s*\d{2}:\d{2})?\b", str(text).strip()))


def _format_editorial_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(round(float(seconds))))
    minutes, secs = divmod(total_seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


__all__ = [
    "_extract_official_curve_points",
    "_filter_meaningful_curve_dips",
    "_pick_curve_windows",
    "_curve_point_from_window",
    "_build_curve_focus_windows",
    "_build_curve_drop_moments",
    "_rebase_action_items_to_curve",
    "_rebuild_editorial_lists",
    "_build_editorial_seek_targets",
    "_is_keep_action",
    "_timed_instruction_line",
    "_compact_editorial_text",
    "_looks_timed_line",
    "_format_editorial_timestamp",
]
