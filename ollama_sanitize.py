"""Post-LLM sanitization helpers for the simplified-review flow.

Lifted out of :mod:`ollama_runtime` in Stage-2 / G4. These functions all
operate on the single-variant review dict produced by ``generate_review``
after the LLM (or the strict-fallback builder) has filled in the simplified
copy. Responsibilities:

* :func:`_apply_simple_cleanup` and its ``_simplify_*`` helpers — rewrite the
  Russian metric labels, focus-window labels, action-item titles, and
  speech-block strings into the simplified-mode wording.
* :func:`_replace_text_field` / :func:`_replace_string_list` /
  :func:`_replace_plan_items` — merge structured LLM output back into the
  fallback dict.
* :func:`_sanitize_generated_copy` — the final pass that strips banned phrases
  ("plot", "ending", "TRIBE", etc.) and re-shapes any malformed action items.

Pure data + small string/regex helpers — no HTTP, no engine state. The only
upstream is :mod:`stdlib`.
"""

from __future__ import annotations

import re
from typing import Any


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
