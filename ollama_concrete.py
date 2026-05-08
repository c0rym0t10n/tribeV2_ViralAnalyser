"""Strict-fallback copy builders for the simplified-review flow.

Lifted out of :mod:`ollama_runtime` in Stage-2 / G4. When the local Ollama
server is unreachable (or returns no parseable structured reply), the runtime
calls :func:`_build_strict_simple_copy` to assemble a deterministic Russian
review from a hand-written copy library + the metric scores already on the
review dict. Functions in this module:

* :func:`_build_strict_simple_copy` — the entry point ``ollama_runtime`` calls.
  Walks the review and rewrites ``action_items``, ``focus_windows``,
  ``strengths``, ``weaknesses``, the executive / product / verdict header,
  the overview banner, and the recommendation plan.
* ``_action_library`` and ``_action_variant`` — the per-metric-key Russian
  copy tables that drive the focus-window relabelling and the action-item
  titles. Parallel to ``_native_action_library_en`` /
  ``_native_action_variant_en`` in :mod:`report_localization` (a future PR
  could consolidate the two translation halves into a single
  ``ACTION_LIBRARY_{RU,EN}`` pair living next to the rest of the localised
  copy; out of scope for G4).
* ``_compact_instruction`` and ``_format_seconds_for_copy`` — small text
  utilities used by the builders.

The ``_compact_instruction`` helper imports ``_clean_sentence`` from
:mod:`ollama_sanitize` (the post-LLM sanitiser already owns that helper).
"""

from __future__ import annotations

from typing import Any

from ollama_sanitize import _clean_sentence


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
