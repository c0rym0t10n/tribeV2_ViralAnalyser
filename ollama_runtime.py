from __future__ import annotations


import json
from copy import deepcopy
from functools import lru_cache
from typing import Any
from urllib.error import URLError

from ollama_http import (
    OLLAMA_BASE_URL,  # noqa: F401  (re-exported for legacy ``ollama_runtime.OLLAMA_BASE_URL`` callers)
    OLLAMA_TIMEOUT_SECONDS,  # noqa: F401  (re-exported for legacy callers)
    request_json as _request_json,
    rewrite_with_ollama as _rewrite_with_ollama,
)

from ollama_sanitize import (
    _apply_simple_cleanup,
    _replace_plan_items,
    _replace_string_list,
    _replace_text_field,
    _sanitize_generated_copy,
)

from ollama_concrete import _build_strict_simple_copy


PREFERRED_MODELS = (
    "qwen3.5:9b",
    "qwen35-27b-q4km:latest",
    "qwen35-27b-q3km:latest",
)


@lru_cache(maxsize=1)
def get_preferred_model() -> str | None:
    try:
        response = _request_json("/tags")
    except (OSError, URLError, json.JSONDecodeError):
        return None

    models = response.get("models")
    if not isinstance(models, list):
        return None

    names = [item.get("name") for item in models if isinstance(item, dict) and item.get("name")]
    for preferred in PREFERRED_MODELS:
        if preferred in names:
            return preferred
    for name in names:
        if "qwen" in str(name).lower():
            return str(name)
    return str(names[0]) if names else None


def simplify_review_copy(review: dict[str, Any]) -> dict[str, Any]:
    analysis_mode = review.get("analysis_mode") or {}
    if analysis_mode.get("key") != "simplified":
        return review
    prepared = deepcopy(review)
    _apply_simple_cleanup(prepared)
    fallback = deepcopy(prepared)
    _build_strict_simple_copy(fallback)
    model = get_preferred_model()
    if not model:
        _sanitize_generated_copy(fallback)
        fallback["copy_rewrite"] = {"provider": "fallback"}
        return fallback

    prompt_payload = _build_review_prompt_payload(prepared)

    schema = {
        "type": "object",
            "properties": {
                "executive_summary": {"type": "string"},
                "product_summary": {"type": "string"},
                "verdict": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "recommendation_plan": {"type": "array", "items": {"type": "string"}},
                "action_items": {"type": "array", "items": {"type": "string"}},
            },
        "required": [
            "executive_summary",
            "product_summary",
            "verdict",
            "strengths",
            "weaknesses",
            "recommendation_plan",
            "action_items",
        ],
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You write the final simplified Russian review directly from structured output of a video-analysis model. "
                "Do not paraphrase stock templates. Base every verdict and recommendation only on the provided metrics, timings, weak spots, and speech data. "
                "Give concrete editing advice. Use short sentences. Keep timestamps. "
                "Do not use jargon or research language. Do not use the words TRIBE, signal, local drop, "
                "turbulence, payoff, plot, ending, final, virality, artifact. "
                "Do not explain why. There must be no field or phrase named 'Почему'. "
                "Do not assume the video has a story. Avoid advice about endings or plot twists. "
                "Every recommendation must say what exactly to edit. "
                "If the data is mixed, say that it is mixed. Do not call every weak score a bad video. "
                "Different videos must not receive the same wording unless the data is genuinely similar. "
                "Bad: 'проверь кадр', 'улучши удержание внимания', 'не трогай ровность ролика'. "
                "Good: 'подрежь затянутый отрезок', 'смени кадр раньше', 'убери лишний текст из кадра', "
                "'покажи товар крупнее', 'скажи главную фразу раньше', 'убери паузу'. "
                "Do not recommend edits in the first 3 seconds or in the last 5 seconds of the video timeline. "
                "Return only these fields: verdict, executive_summary, product_summary, strengths, weaknesses, recommendation_plan, action_items. "
                "strengths and weaknesses must be arrays of short strings. "
                "recommendation_plan must be an array of short strings. "
                "action_items must be an array of short strings, each starting with a timestamp like 00:09 or a range like 00:04-00:09. "
                "Do not add any other fields. Use compact JSON. "
                "Return valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                "Rewrite this review for simplified mode. "
                "The person should immediately understand what to change in the video.\n"
                f"{json.dumps(prompt_payload, ensure_ascii=False)}"
            ),
        },
    ]

    rewritten = _rewrite_with_ollama(model, messages, schema)
    if not isinstance(rewritten, dict):
        _sanitize_generated_copy(fallback)
        fallback["copy_rewrite"] = {"provider": "fallback", "fallback_reason": "ollama_no_structured_reply"}
        return fallback

    updated = deepcopy(fallback)
    _replace_text_field(updated, rewritten, "executive_summary")
    _replace_text_field(updated, rewritten, "product_summary")
    _replace_text_field(updated, rewritten, "verdict")
    _replace_string_list(updated, rewritten, "strengths", 3)
    _replace_string_list(updated, rewritten, "weaknesses", 3)
    _replace_plan_items(updated, rewritten)
    _sanitize_generated_copy(updated)
    updated["copy_rewrite"] = {"provider": "ollama", "model": model, "mode": "structured_review_writer"}
    return updated


def _speech_prompt_payload(speech: Any) -> dict[str, Any]:
    if not isinstance(speech, dict):
        return {"available": False}
    return {
        "available": bool(speech.get("available")),
        "speech_start_seconds": speech.get("speech_start_seconds"),
        "pause_ratio": speech.get("pause_ratio"),
        "message": speech.get("message"),
        "note": speech.get("note"),
    }


def _build_review_prompt_payload(review: dict[str, Any]) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    for item in review.get("metrics", []):
        if not isinstance(item, dict):
            continue
        metrics.append(
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "score": item.get("score"),
                "raw_value": item.get("raw_value"),
            }
        )

    focus_windows: list[dict[str, Any]] = []
    for item in review.get("focus_windows", []):
        if not isinstance(item, dict):
            continue
        focus_windows.append(
            {
                "label": item.get("label"),
                "timestamp": item.get("timestamp"),
                "seconds": item.get("seconds"),
            }
        )

    drop_moments: list[dict[str, Any]] = []
    for item in review.get("drop_moments", []):
        if not isinstance(item, dict):
            continue
        drop_moments.append(
            {
                "timestamp": item.get("timestamp"),
                "seconds": item.get("seconds"),
            }
        )

    timeline = review.get("timeline") if isinstance(review.get("timeline"), dict) else {}
    return {
        "overall_score": review.get("overall_score"),
        "score_scale": "0-100 internal review score built from the metrics below",
        "metric_definitions": {
            "early_response": "proxy for how strong the opening feels relative to the rest of the same video",
            "sustain": "proxy for how well the later part holds up relative to the start; this is not platform retention",
            "transition": "proxy for density of new visual events over time; this is not a literal scene-cut detector",
            "stability": "proxy for how evenly the visual stream reads; this is not OCR or clutter detection",
            "density": "proxy for overall visual strength relative to the video's own peaks; this is not a direct brightness or contrast detector",
        },
        "evidence_limits": {
            "speech_available": bool((review.get("speech") or {}).get("available")),
            "on_screen_text_detection": False,
            "scene_cut_detection": False,
            "camera_stability_detection": False,
        },
        "metrics": metrics,
        "timeline": {
            "duration_seconds": timeline.get("duration_seconds"),
            "avg_score": timeline.get("avg_score"),
            "max_score": timeline.get("max_score"),
            "min_score": timeline.get("min_score"),
        },
        "focus_windows": focus_windows[:3],
        "drop_moments": drop_moments[:4],
        "speech": _speech_prompt_payload(review.get("speech")),
    }
