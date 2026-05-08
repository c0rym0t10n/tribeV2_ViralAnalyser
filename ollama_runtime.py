from __future__ import annotations


import json
from copy import deepcopy
from functools import lru_cache
import re
from typing import Any
from urllib.error import URLError

from ollama_http import (
    OLLAMA_BASE_URL,  # noqa: F401  (re-exported for legacy ``ollama_runtime.OLLAMA_BASE_URL`` callers)
    OLLAMA_TIMEOUT_SECONDS,  # noqa: F401  (re-exported for legacy callers)
    request_json as _request_json,
    rewrite_with_ollama as _rewrite_with_ollama,
)


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


def _apply_simple_cleanup(review: dict[str, Any]) -> None:
    review["signal_note"] = "Ниже простая подсказка: где ролик выглядит лучше и где его стоит править первым."
    _simplify_metrics(review)
    _simplify_focus_windows(review)
    _simplify_action_items(review)
    _simplify_speech(review)


def _simplify_metrics(review: dict[str, Any]) -> None:
    metrics = review.get("metrics")
    if not isinstance(metrics, list):
        return

    key_label_map = {
        "early_response": "Хук",
        "sustain": "Удержание",
        "transition": "Темп",
        "stability": "Чистота кадра",
        "density": "Сила визуала",
    }
    label_map = {
        "Первые секунды": "Хук",
        "Держит внимание": "Удержание",
        "Смена кадра": "Темп",
        "Ровность ролика": "Чистота кадра",
        "Общая сила": "Сила визуала",
        "Ранний отклик": "Хук",
        "Устойчивость отклика": "Удержание",
        "Плотность переходов": "Темп",
        "Стабильность сигнала": "Чистота кадра",
        "Плотность активации": "Сила визуала",
        "Р В Р В°Р Р…Р Р…Р С‘Р в„– Р С•РЎвЂљР С”Р В»Р С‘Р С”": "Хук",
        "Р Р€РЎРѓРЎвЂљР С•Р в„–РЎвЂЎР С‘Р Р†Р С•РЎРѓРЎвЂљРЎРЉ Р С•РЎвЂљР С”Р В»Р С‘Р С”Р В°": "Удержание",
        "Р СџР В»Р С•РЎвЂљР Р…Р С•РЎРѓРЎвЂљРЎРЉ Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘Р С•Р Р†": "Темп",
        "Р РЋРЎвЂљР В°Р В±Р С‘Р В»РЎРЉР Р…Р С•РЎРѓРЎвЂљРЎРЉ РЎРѓР С‘Р С–Р Р…Р В°Р В»Р В°": "Чистота кадра",
        "Р СџР В»Р С•РЎвЂљР Р…Р С•РЎРѓРЎвЂљРЎРЉ Р В°Р С”РЎвЂљР С‘Р Р†Р В°РЎвЂ Р С‘Р С‘": "Сила визуала",
    }
    summary_map = {
        "Хук": {
            "high": "С первого кадра уже понятно, на что смотреть: главный объект или действие видны сразу.",
            "mid": "Начало нормальное, но главный объект или действие можно показать раньше и крупнее.",
            "low": "Первые секунды слабые: главное появляется слишком поздно или его плохо видно сразу.",
        },
        "Удержание": {
            "high": "По ходу ролика есть новые кадры или действия, поэтому интерес не падает.",
            "mid": "Интерес держится не везде: есть куски, где долго не происходит ничего нового.",
            "low": "Есть куски без нового действия или новой картинки, поэтому ролик хочется промотать.",
        },
        "Темп": {
            "high": "Кадры меняются вовремя: один план не висит дольше, чем нужно.",
            "mid": "Смена кадров есть, но местами один и тот же план держится чуть дольше, чем надо.",
            "low": "Кадры меняются слишком поздно: один и тот же план зависает, и ролик начинает тянуться.",
        },
        "Чистота кадра": {
            "high": "В кадре легко понять главное: один объект или одно действие сразу забирают внимание.",
            "mid": "Иногда в кадре сразу слишком много всего: несколько предметов, мелкий текст или пестрый фон.",
            "low": "В кадре слишком много лишнего: фон, текст и детали спорят между собой, и главное теряется.",
        },
        "Сила визуала": {
            "high": "Картинка сильная: объект видно хорошо, движение читается, контраст не теряется.",
            "mid": "Картинка нормальная, но объект местами мелкий, движения мало или не хватает контраста.",
            "low": "Картинка слабая: мало крупности, движения или контраста, поэтому кадр не цепляет.",
        },
    }

    for item in metrics:
        if not isinstance(item, dict):
            continue
        metric_key = str(item.get("key") or "")
        label = str(item.get("label") or "")
        simple_label = key_label_map.get(metric_key) or label_map.get(label, label)
        item["label"] = simple_label
        score = int(item.get("score") or 0)
        bucket = "high" if score >= 75 else "mid" if score >= 60 else "low"
        item["summary"] = summary_map.get(simple_label, {}).get(bucket, item.get("summary", ""))


def _simplify_focus_windows(review: dict[str, Any]) -> None:
    windows = review.get("focus_windows")
    if not isinstance(windows, list):
        return
    title_map = {
        "Сильный момент": "Лучший кусок",
        "Слабое место": "Где чинить первым",
        "Резкая смена": "Где ускорить",
        "Пик сигнала": "Лучший кусок",
        "Слабое окно": "Где чинить первым",
        "Самый резкий переход": "Где ускорить",
        "РЎРёР»СЊРЅС‹Р№ РјРѕРјРµРЅС‚": "Лучший кусок",
        "РЎР»Р°Р±РѕРµ РјРµСЃС‚Рѕ": "Где чинить первым",
        "Р РµР·РєР°СЏ СЃРјРµРЅР°": "Где ускорить",
        "РџРёРє СЃРёРіРЅР°Р»Р°": "Лучший кусок",
        "РЎР»Р°Р±РѕРµ РѕРєРЅРѕ": "Где чинить первым",
        "РЎР°РјС‹Р№ СЂРµР·РєРёР№ РїРµСЂРµС…РѕРґ": "Где ускорить",
    }
    summary_map = {
        "Лучший кусок": "Здесь ролик выглядит сильнее всего.",
        "Где чинить первым": "Начни правки с этого места.",
        "Где ускорить": "Здесь особенно полезно сократить кусок или быстрее перейти к следующему моменту.",
    }
    for item in windows:
        if not isinstance(item, dict):
            continue
        title = str(item.get("label") or "")
        simple_title = title_map.get(title, title)
        item["label"] = simple_title
        if simple_title in summary_map:
            item["summary"] = summary_map[simple_title]


def _simplify_action_items(review: dict[str, Any]) -> None:
    items = review.get("action_items")
    if not isinstance(items, list):
        return
    title_map = {
        "Исправить слабое место": "Исправить это место",
        "Сохранить сильный кусок": "Оставить как есть",
        "Подтянуть локальную просадку": "Проверить этот кусок",
        "Подключить речь раньше": "Сказать главное раньше",
        "РСЃРїСЂР°РІРёС‚СЊ СЃР»Р°Р±РѕРµ РѕРєРЅРѕ": "Исправить это место",
        "РЎРѕС…СЂР°РЅРёС‚СЊ СЃРёР»СЊРЅС‹Р№ РјРѕРјРµРЅС‚": "Оставить как есть",
        "РџРѕРґС‚СЏРЅСѓС‚СЊ Р»РѕРєР°Р»СЊРЅСѓСЋ РїСЂРѕСЃР°РґРєСѓ": "Проверить этот кусок",
        "РџРѕРґРєР»СЋС‡РёС‚СЊ СЂРµС‡СЊ СЂР°РЅСЊС€Рµ": "Сказать главное раньше",
    }
    instruction_rewrites = (
        ("локальную просадку", "слабое место"),
        ("TRIBE-сигнала", "ролика"),
        ("TRIBE", ""),
        ("сигнал", "ролик"),
        ("просад", "слабое место"),
        ("Почему:", ""),
        ("Почему", ""),
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        item["title"] = title_map.get(title, title)
        instruction = " ".join(str(item.get("instruction") or "").split())
        for old, new in instruction_rewrites:
            instruction = instruction.replace(old, new)
        item["instruction"] = instruction.strip(" -,:")
        item["why"] = ""


def _simplify_speech(review: dict[str, Any]) -> None:
    speech = review.get("speech")
    if not isinstance(speech, dict):
        return
    if speech.get("available"):
        speech["note"] = "Ниже текст речи из ролика. Он помогает понять, какие слова прозвучали и где."
    else:
        speech["note"] = "Речь в этом ролике разобралась неуверенно. Смотри в первую очередь на кадр, темп и смену сцен."
        speech["message"] = "Речь в этом ролике разобралась неуверенно."

    metrics = speech.get("metrics")
    if not isinstance(metrics, list):
        return
    metric_names = {
        "Старт речи": "Когда начинается речь",
        "Слов в секунду": "Темп речи",
        "Плотность артикуляции": "Насколько плотно сказано",
        "Доля пауз": "Сколько пауз",
        "Уверенность ASR": "Насколько хорошо разобралась речь",
        "РЎС‚Р°СЂС‚ СЂРµС‡Рё": "Когда начинается речь",
        "РЎР»РѕРІ РІ СЃРµРєСѓРЅРґСѓ": "Темп речи",
        "РџР»РѕС‚РЅРѕСЃС‚СЊ Р°СЂС‚РёРєСѓР»СЏС†РёРё": "Насколько плотно сказано",
        "Р”РѕР»СЏ РїР°СѓР·": "Сколько пауз",
        "РЈРІРµСЂРµРЅРЅРѕСЃС‚СЊ ASR": "Насколько хорошо разобралась речь",
    }
    for item in metrics:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        item["label"] = metric_names.get(label, label)


def _replace_text_field(target: dict[str, Any], source: dict[str, Any], key: str) -> None:
    value = source.get(key)
    if isinstance(value, str) and value.strip():
        target[key] = _clean_sentence(value)


def _replace_string_list(target: dict[str, Any], source: dict[str, Any], key: str, limit: int) -> None:
    items = source.get(key)
    if isinstance(items, str):
        items = _split_copy_lines(items)
    if not isinstance(items, list):
        return
    cleaned = [_clean_sentence(item) for item in items if isinstance(item, str) and item.strip()]
    if cleaned:
        target[key] = cleaned[:limit]


def _replace_plan_items(target: dict[str, Any], source: dict[str, Any]) -> None:
    items = source.get("recommendation_plan")
    if isinstance(items, str):
        items = _split_copy_lines(items)
    if not isinstance(items, list):
        return
    cleaned: list[dict[str, str]] = []
    titles = ("Сделать первым", "Сделать потом", "Проверить после правок")
    for item in items:
        if isinstance(item, dict):
            title = item.get("title")
            detail = item.get("detail")
            if not isinstance(title, str) or not isinstance(detail, str):
                continue
            if not title.strip() or not detail.strip():
                continue
            cleaned.append({"title": _clean_sentence(title), "detail": _clean_sentence(detail)})
            continue
        if not isinstance(item, str) or not item.strip():
            continue
        detail = _clean_sentence(item)
        if not detail:
            continue
        title = titles[min(len(cleaned), len(titles) - 1)]
        cleaned.append({"title": title, "detail": detail})
    if cleaned:
        target["recommendation_plan"] = cleaned[:3]


def _split_copy_lines(value: str) -> list[str]:
    text = " ".join(str(value).strip().split())
    if not text:
        return []
    parts = re.split(r"(?:\s*[•\n;]+\s*|\.\s+)", text)
    return [part.strip(" -,:.") for part in parts if part.strip(" -,:.")]


def _coerce_action_line(value: str) -> dict[str, str] | None:
    raw_text = " ".join(str(value).strip().split())
    if not raw_text:
        return None
    match = re.search(r"\b\d{2}:\d{2}(?:\s*[-–]\s*\d{2}:\d{2})?\b", raw_text)
    if not match:
        return None
    timestamp = re.sub(r"\s+", "", match.group(0))
    instruction_text = f"{raw_text[:match.start()]} {raw_text[match.end():]}".strip(" -,:.")
    instruction = _clean_sentence(instruction_text)
    if not instruction:
        return None
    title = _short_action_title(instruction)
    return {
        "timestamp": timestamp,
        "title": title,
        "instruction": instruction,
        "why": "",
    }


def _short_action_title(instruction: str) -> str:
    head = instruction.split(".", 1)[0].split(",", 1)[0].strip()
    words = head.split()
    if not words:
        return "Что сделать"
    compact = " ".join(words[:4])
    return compact[:42].rstrip(" -,:.")


def _clean_sentence(value: str) -> str:
    text = " ".join(str(value).strip().split())
    banned = (
        "TRIBE",
        "сигнал",
        "просад",
        "турбул",
        "payoff",
        "сюжет",
        "финал",
        "конец видео",
        "вираль",
        "артефакт",
        "Почему:",
        "Почему",
    )
    for token in banned:
        text = text.replace(token, "")
    return " ".join(text.split()).strip(" -,:")


def _sanitize_generated_copy(review: dict[str, Any]) -> None:
    speech = review.get("speech") if isinstance(review.get("speech"), dict) else {}
    speech_available = bool(speech.get("available"))

    replacements = [
        ("убери лишний текст из кадра", "убери лишнее из кадра"),
        ("лишний текст", "лишнее"),
        ("текст на экране", "лишние детали"),
        ("очисти кадр от лишнего", "сделай главное заметнее"),
        ("убери лишнее из кадра", "сделай главное заметнее"),
        ("кадр перегружен деталями", "главное считывается неуверенно"),
        ("смени кадр раньше", "добавь более раннюю смену плана"),
        ("смени сцену раньше", "добавь более раннюю смену плана"),
        ("ускорь переходы", "собери темп плотнее"),
        ("переходы между сценами", "темп этого куска"),
        ("смены кадров", "новых визуальных моментов"),
        ("смена кадров", "новые визуальные моменты"),
        ("отсутствие смены кадров", "мало новых визуальных моментов"),
        ("грязный кадр", "нечёткий визуальный акцент"),
        ("дрожит", "читается неуверенно"),
        ("темный", "менее читаемый"),
    ]
    if not speech_available:
        replacements.extend(
            [
                ("сократи паузы", "сократи затянутый кусок"),
                ("убери паузу", "подрежь пустой промежуток"),
                ("паузы", "затянутые места"),
                ("скажи главную фразу раньше", "покажи главное раньше"),
                ("речь", "подача"),
            ]
        )

    def transform(text: str) -> str:
        updated = str(text)
        updated = re.sub(r"\bвидео начинается(\s+только)?\s+с\b", r"Речь начинается\1 с", updated, flags=re.IGNORECASE)
        updated = re.sub(r"\bвидео начинается(\s+только)?\s+на\b", r"Речь начинается\1 на", updated, flags=re.IGNORECASE)
        updated = re.sub(r"\bвидео стартует(\s+только)?\s+с\b", r"Речь начинается\1 с", updated, flags=re.IGNORECASE)
        updated = re.sub(r"\bвидео стартует(\s+только)?\s+на\b", r"Речь начинается\1 на", updated, flags=re.IGNORECASE)
        for old, new in replacements:
            updated = re.sub(re.escape(old), new, updated, flags=re.IGNORECASE)
        return _clean_sentence(updated)

    for key in ("verdict", "executive_summary", "product_summary"):
        value = review.get(key)
        if isinstance(value, str) and value.strip():
            review[key] = transform(value)

    for key in ("strengths", "weaknesses"):
        items = review.get(key)
        if isinstance(items, list):
            review[key] = [transform(item) for item in items if isinstance(item, str) and transform(item)]

    plan = review.get("recommendation_plan")
    if isinstance(plan, list):
        cleaned_plan: list[dict[str, str]] = []
        for item in plan:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            detail = transform(str(item.get("detail") or ""))
            if title and detail:
                cleaned_plan.append({"title": title, "detail": detail})
        review["recommendation_plan"] = cleaned_plan[:3]

    actions = review.get("action_items")
    if isinstance(actions, list):
        cleaned_actions: list[dict[str, str]] = []
        for item in actions:
            if not isinstance(item, dict):
                continue
            timestamp = str(item.get("timestamp") or "").strip()
            title = transform(str(item.get("title") or ""))
            instruction = transform(str(item.get("instruction") or ""))
            if timestamp and title and instruction:
                cleaned_actions.append(
                    {
                        "timestamp": timestamp,
                        "title": title,
                        "instruction": instruction,
                        "why": "",
                    }
                )
        review["action_items"] = cleaned_actions[:4]


def _build_strict_simple_copy(review: dict[str, Any]) -> None:
    metrics = _ordered_metrics(review)
    actions = _build_concrete_action_items(review, metrics)
    if actions:
        review["action_items"] = actions
    _rewrite_focus_windows(review, metrics)
    review["recommendation_plan"] = _build_concrete_plan(review)
    review["strengths"] = _build_concrete_strengths(review, metrics)
    review["weaknesses"] = _build_concrete_weaknesses(review)
    verdict, executive_summary, product_summary = _build_concrete_header(review)
    review["verdict"] = verdict
    review["executive_summary"] = executive_summary
    review["product_summary"] = product_summary


def _ordered_metrics(review: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = review.get("metrics")
    if not isinstance(metrics, list):
        return []
    collected: list[dict[str, Any]] = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        collected.append(
            {
                "key": key,
                "label": str(item.get("label") or "").strip(),
                "score": int(item.get("score") or 0),
            }
        )
    return sorted(collected, key=lambda item: item["score"], reverse=True)


def _action_library(metric_key: str) -> dict[str, str]:
    library = {
        "early_response": {
            "title": "Покажи главное раньше",
            "instruction": "Покажи главное с первого кадра, убери длинный заход и скажи главную фразу раньше.",
            "keep": "Оставь этот старт как ориентир. Здесь уже быстро понятно, что происходит.",
            "focus_label": "Где усилить начало",
            "focus_summary": "Покажи главное раньше и убери длинный заход.",
        },
        "sustain": {
            "title": "Подрежь затянутый отрезок",
            "instruction": "Убери 1-2 секунды перед этой точкой или быстрее переведи ролик к следующему действию.",
            "keep": "Оставь этот кусок как ориентир. Здесь темп уже держится.",
            "focus_label": "Где сократить",
            "focus_summary": "Подрежь затянутый отрезок или раньше переведи ролик к следующему действию.",
        },
        "transition": {
            "title": "Смени кадр раньше",
            "instruction": "Смени план, ракурс или действие раньше, чтобы этот участок не тянулся.",
            "keep": "Оставь здесь текущий темп как ориентир. Этот кусок уже не тянется.",
            "focus_label": "Где ускорить",
            "focus_summary": "Здесь лучше раньше сменить план или добавить новый визуальный акцент.",
        },
        "stability": {
            "title": "Сделай главное заметнее",
            "instruction": "Сделай главное заметнее: крупнее объект, чище фон или меньше конкурирующих деталей.",
            "keep": "Оставь этот кусок как ориентир. Здесь главное читается лучше.",
            "focus_label": "Где сделать главное заметнее",
            "focus_summary": "Здесь лучше сильнее выделить главное и убрать лишние детали.",
        },
        "density": {
            "title": "Покажи товар крупнее",
            "instruction": "Покажи объект крупнее, добавь движение в кадре или усили контраст.",
            "keep": "Оставь здесь текущую крупность и контраст. Этот кусок выглядит сильнее остальных.",
            "focus_label": "Где усилить картинку",
            "focus_summary": "Покажи объект крупнее или добавь более заметное действие.",
        },
        "speech_start": {
            "title": "Скажи главное раньше",
            "instruction": "Скажи главную фразу до этой точки или сократи немой заход.",
            "keep": "",
            "focus_label": "Где дать фразу раньше",
            "focus_summary": "Скажи главную фразу раньше и сократи немой заход.",
        },
        "pause": {
            "title": "Ускорь затянутый кусок",
            "instruction": "Сократи затянутый кусок и убери пустой промежуток.",
            "keep": "",
            "focus_label": "Где ускорить подачу",
            "focus_summary": "Здесь лучше убрать пустой промежуток и ускорить подачу.",
        },
    }
    return library.get(metric_key, library["sustain"])


def _window_at(review: dict[str, Any], index: int) -> dict[str, Any] | None:
    windows = review.get("focus_windows")
    if not isinstance(windows, list) or index >= len(windows):
        return None
    item = windows[index]
    return item if isinstance(item, dict) else None


def _drop_timestamp_candidates(review: dict[str, Any]) -> list[str]:
    moments = review.get("drop_moments")
    if not isinstance(moments, list):
        return []
    result: list[str] = []
    for item in moments:
        if isinstance(item, dict):
            timestamp = str(item.get("timestamp") or "").strip()
            if timestamp:
                result.append(timestamp)
    return result


def _speech_action(review: dict[str, Any]) -> tuple[str | None, str] | None:
    speech = review.get("speech")
    if not isinstance(speech, dict) or not speech.get("available"):
        return None
    if isinstance(speech.get("speech_start_seconds"), (int, float)) and float(speech["speech_start_seconds"]) > 3.0:
        return _format_seconds_for_copy(float(speech["speech_start_seconds"])), "speech_start"
    if isinstance(speech.get("pause_ratio"), (int, float)) and float(speech["pause_ratio"]) > 0.28:
        return None, "pause"
    return None


def _build_concrete_action_items(review: dict[str, Any], metrics: list[dict[str, Any]]) -> list[dict[str, str]]:
    weakest = metrics[-1] if metrics else {"key": "sustain"}
    runner = metrics[-2] if len(metrics) > 1 else weakest
    third = metrics[-3] if len(metrics) > 2 else runner
    weak_window = _window_at(review, 1) or _window_at(review, 0)

    items: list[dict[str, str]] = []
    used_timestamps: set[str] = set()

    drop_timestamps = _drop_timestamp_candidates(review)
    metric_keys = [str(weakest["key"]), str(runner["key"]), str(third["key"]), "transition"]

    if not drop_timestamps and weak_window and weak_window.get("timestamp"):
        drop_timestamps = [str(weak_window["timestamp"])]

    speech_action = _speech_action(review)
    if speech_action and len(drop_timestamps) < 4:
        timestamp, metric_key = speech_action
        if timestamp and timestamp not in drop_timestamps:
            drop_timestamps.append(timestamp)
            metric_keys.append(metric_key)

    title_counts: dict[str, int] = {}
    metric_counts: dict[str, int] = {}
    for index, timestamp in enumerate(drop_timestamps):
        metric_key = metric_keys[min(index, len(metric_keys) - 1)]
        item = _make_action_item(timestamp, metric_key, metric_counts.get(metric_key, 0))
        metric_counts[metric_key] = metric_counts.get(metric_key, 0) + 1
        if item["title"] in title_counts:
            item = _make_action_item(timestamp, metric_key, metric_counts[metric_key])
            metric_counts[metric_key] += 1
        title_counts[item["title"]] = title_counts.get(item["title"], 0) + 1
        items.append(item)

    deduped: list[dict[str, str]] = []
    for item in items:
        timestamp = item["timestamp"]
        if not timestamp or timestamp in used_timestamps:
            continue
        used_timestamps.add(timestamp)
        deduped.append(item)
    return deduped[:4]


def _action_variant(metric_key: str, variant_index: int) -> dict[str, str]:
    variants = {
        "early_response": [
            {"title": "Покажи главное раньше", "instruction": "Перенеси главный кадр или оффер ближе к этой точке. Убери длинный заход перед ним."},
            {"title": "Начни с результата", "instruction": "Поставь перед этой точкой кадр, где сразу понятно, что получит зритель."},
            {"title": "Убери подводку", "instruction": "Если перед этим местом есть вступление, вырежи его и начни ближе к действию."},
        ],
        "sustain": [
            {"title": "Подрежь затянутый отрезок", "instruction": "Убери 1-2 секунды перед этой точкой или быстрее переведи ролик к следующему действию."},
            {"title": "Добавь новый поворот", "instruction": "Перед этой точкой вставь новую деталь, движение или смену плана, чтобы ролик не провисал."},
            {"title": "Собери темп плотнее", "instruction": "Сожми паузу и оставь только кадры, которые двигают сцену вперед."},
        ],
        "transition": [
            {"title": "Смени кадр раньше", "instruction": "Смени план, ракурс или действие раньше, чтобы этот участок не тянулся."},
            {"title": "Добавь визуальный акцент", "instruction": "Перед этой точкой добавь движение, жест, приближение или смену крупности."},
            {"title": "Убери зависший план", "instruction": "Если кадр стоит без нового действия, сократи его до первого понятного движения."},
        ],
        "stability": [
            {"title": "Убери лишнее из кадра", "instruction": "Оставь один главный объект и убери лишние детали или текст рядом с ним."},
            {"title": "Сделай фокус понятнее", "instruction": "Подсвети главный объект крупностью, положением в кадре или более чистым фоном."},
            {"title": "Разгрузи композицию", "instruction": "Убери конкурирующие элементы, чтобы взгляд не распадался между несколькими деталями."},
        ],
        "density": [
            {"title": "Покажи товар крупнее", "instruction": "Сделай объект крупнее, усили движение в кадре или добавь контраст."},
            {"title": "Усиль визуальный удар", "instruction": "Перед этой точкой добавь более яркий кадр, крупный план или заметное действие."},
            {"title": "Сделай кадр контрастнее", "instruction": "Отдели главный объект от фона светом, цветом или более чистой композицией."},
        ],
        "speech_start": [
            {"title": "Скажи главное раньше", "instruction": "Подай главную фразу до этой точки и сократи немой заход."},
            {"title": "Перенеси фразу вперед", "instruction": "Поставь ключевую реплику ближе к началу слабого участка."},
        ],
        "pause": [
            {"title": "Убери паузу", "instruction": "Подрежь пустой промежуток или скажи фразу плотнее, чтобы участок не проседал."},
            {"title": "Сожми речь", "instruction": "Сократи паузу между словами и оставь только нужную фразу."},
        ],
    }
    options = variants.get(metric_key)
    if not options:
        base = _action_library(metric_key)
        return {"title": base["title"], "instruction": base["instruction"]}
    return options[variant_index % len(options)]


def _make_action_item(timestamp: str, metric_key: str, variant_index: int = 0) -> dict[str, str]:
    action = _action_variant(metric_key, variant_index)
    return {
        "timestamp": timestamp,
        "title": action["title"],
        "instruction": action["instruction"],
        "why": "",
    }


def _rewrite_focus_windows(review: dict[str, Any], metrics: list[dict[str, Any]]) -> None:
    windows = review.get("focus_windows")
    if not isinstance(windows, list):
        return
    strongest = metrics[0]["key"] if metrics else "sustain"
    weakest = metrics[-1]["key"] if metrics else "sustain"

    if len(windows) >= 1 and isinstance(windows[0], dict):
        windows[0]["label"] = "Лучший кусок"
        windows[0]["summary"] = _action_library(strongest)["keep"] or "Оставь этот кусок как ориентир."
    if len(windows) >= 2 and isinstance(windows[1], dict):
        weak_action = _action_library(weakest)
        windows[1]["label"] = weak_action["focus_label"]
        windows[1]["summary"] = weak_action["focus_summary"]
    if len(windows) >= 3 and isinstance(windows[2], dict):
        transition_action = _action_library("transition")
        windows[2]["label"] = transition_action["focus_label"]
        windows[2]["summary"] = transition_action["focus_summary"]


def _build_concrete_plan(review: dict[str, Any]) -> list[dict[str, str]]:
    actions = review.get("action_items")
    if not isinstance(actions, list):
        return []
    keep_item = next((item for item in actions if isinstance(item, dict) and item.get("title") == "Оставить как есть"), None)
    edit_items = [
        item
        for item in actions
        if isinstance(item, dict) and item.get("title") != "Оставить как есть"
    ]

    plan: list[dict[str, str]] = []
    if keep_item:
        plan.append(
            {
                "title": "Оставить",
                "detail": f"{keep_item['timestamp']}: {_compact_instruction(str(keep_item.get('instruction') or ''))}",
            }
        )
    if edit_items:
        first = edit_items[0]
        plan.append(
            {
                "title": "Сделать первым",
                "detail": f"{first['timestamp']}: {_compact_instruction(str(first.get('instruction') or ''))}",
            }
        )
    if len(edit_items) > 1:
        second = edit_items[1]
        plan.append(
            {
                "title": "Сделать потом",
                "detail": f"{second['timestamp']}: {_compact_instruction(str(second.get('instruction') or ''))}",
            }
        )
    return plan[:3]


def _build_concrete_strengths(review: dict[str, Any], metrics: list[dict[str, Any]]) -> list[str]:
    best_window = _window_at(review, 0)
    strongest = metrics[0]["key"] if metrics else "sustain"
    items: list[str] = []
    if best_window and best_window.get("timestamp"):
        items.append(
            f"{best_window['timestamp']}: {_action_library(strongest)['keep'] or 'Оставь этот кусок как ориентир.'}"
        )
    if strongest == "early_response":
        items.append("Сохрани быстрый заход в начале. Не растягивай вступление новыми вставками.")
    elif strongest == "transition":
        items.append("Сохрани текущий темп смены кадров в сильных местах. Он уже помогает ролику не тянуться.")
    else:
        items.append("Сильные места не перегружай новыми правками. Ориентируйся на их темп и подачу.")
    return items[:2]


def _build_concrete_weaknesses(review: dict[str, Any]) -> list[str]:
    actions = review.get("action_items")
    if not isinstance(actions, list):
        return []
    edit_items = [
        item
        for item in actions
        if isinstance(item, dict) and item.get("title") != "Оставить как есть"
    ]
    items = [
        f"{item['timestamp']}: {_compact_instruction(str(item.get('instruction') or ''))}"
        for item in edit_items[:2]
        if item.get("timestamp")
    ]
    return items[:2]


def _build_concrete_header(review: dict[str, Any]) -> tuple[str, str, str]:
    score = int(review.get("overall_score") or 0)
    actions = review.get("action_items")
    metric_scores = _metric_scores(review)
    if not isinstance(actions, list):
        return (
            _overall_status(score),
            "Ниже отмечены слабые места ролика и простые решения, что именно поменять.",
            "Смотри ниже отмеченные места и правь ролик по одному куску за раз.",
        )

    keep_item = next((item for item in actions if isinstance(item, dict) and item.get("title") == "Оставить как есть"), None)
    edit_items = [
        item
        for item in actions
        if isinstance(item, dict) and item.get("title") != "Оставить как есть"
    ]
    verdict = _overall_status(score)
    executive_summary = _simple_overview_text(metric_scores, len(edit_items))
    product_summary = _simple_banner_text(metric_scores, keep_item is not None, len(edit_items))
    return verdict, executive_summary, product_summary


def _metric_scores(review: dict[str, Any]) -> dict[str, int]:
    metrics = review.get("metrics")
    if not isinstance(metrics, list):
        return {}
    result: dict[str, int] = {}
    for item in metrics:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key:
            result[key] = int(item.get("score") or 0)
    return result


def _overall_status(score: int) -> str:
    if score >= 75:
        return "Ролик сильный."
    if score >= 60:
        return "Ролик нормальный, но нужны правки."
    return "Ролик слабый."


def _simple_overview_text(metric_scores: dict[str, int], edit_count: int) -> str:
    early = metric_scores.get("early_response", 0)
    sustain = metric_scores.get("sustain", 0)
    transition = metric_scores.get("transition", 0)
    stability = metric_scores.get("stability", 0)
    density = metric_scores.get("density", 0)

    if early >= 75:
        start_phrase = "В начале ролик смотрится уверенно"
    elif early >= 60:
        start_phrase = "В начале ролик выглядит нормально"
    else:
        start_phrase = "В начале ролик слабый"

    if sustain < 60:
        middle_phrase = "потом темп проседает"
    elif transition < 60:
        middle_phrase = "потом кадры меняются поздно"
    elif stability < 60:
        middle_phrase = "местами в кадре слишком много лишнего"
    elif density < 60:
        middle_phrase = "местами картинка выглядит слабо"
    else:
        middle_phrase = "дальше ролик держится ровно"

    tail = " Проблемные места отмечены ниже, и рядом уже есть простые решения." if edit_count else " Ниже можно посмотреть отмеченные места ролика."
    return f"{start_phrase}, но {middle_phrase}.{tail}"


def _simple_banner_text(metric_scores: dict[str, int], has_keep_item: bool, edit_count: int) -> str:
    parts: list[str] = []
    if has_keep_item:
        parts.append("Сильные места лучше не ломать")
    if metric_scores.get("transition", 0) < 60:
        parts.append("слабые места чаще всего лечатся более ранней сменой кадра")
    elif metric_scores.get("stability", 0) < 60:
        parts.append("слабые места чаще всего лечатся более чистым кадром")
    elif metric_scores.get("density", 0) < 60:
        parts.append("слабые места чаще всего лечатся более сильной картинкой")
    else:
        parts.append("слабые места отмечены ниже")
    if edit_count:
        parts.append("ниже уже есть конкретные рекомендации, что менять")
    return ". ".join(part[:1].upper() + part[1:] for part in parts) + "."


def _compact_instruction(text: str) -> str:
    cleaned = _clean_sentence(text).strip()
    if not cleaned:
        return ""
    return cleaned if cleaned.endswith(".") else f"{cleaned}."


def _format_seconds_for_copy(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"
