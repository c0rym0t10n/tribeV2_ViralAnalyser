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
    """Rewrite the simplified-mode review dict in place.

    ``language`` is read from ``review["language"]`` (added by ``generate_review``
    in S1-1) and threaded down so each helper picks the matching summary table.
    Defaults to ES when the field is missing — the engine never emits without
    it, but a robust fallback keeps the output intelligible if a stale review
    dict slips in from an older code path.
    """
    language = str(review.get("language") or "es").strip().lower()
    review["signal_note"] = _signal_note_for_language(language)
    _simplify_metrics(review, language)
    _simplify_focus_windows(review, language)
    _simplify_action_items(review, language)
    _simplify_speech(review, language)


def _signal_note_for_language(language: str) -> str:
    if language == "en":
        return "A quick read of where the cut works and where to fix first."
    return "Pista rápida: dónde el cut jala y por dónde empezar a arreglar."


# Simplified-mode metric labels stay in EN jargon (hook / retention / pacing
# / visual clarity / visual punch) regardless of report language. The bug
# fixed here was the prior leak of RU labels (``Темп``…) when language="en".
_SIMPLIFIED_METRIC_LABELS_EN_JARGON = {
    "early_response": "Hook",
    "sustain": "Retention",
    "transition": "Pacing",
    "stability": "Visual clarity",
    "density": "Visual punch",
}

_SIMPLIFIED_METRIC_SUMMARY_ES = {
    "Hook": {
        "high": "Desde el primer shot ya está claro qué ver: el objeto principal o la acción se notan de volada.",
        "mid": "El arranque está bien, pero lo principal se podría mostrar antes y más grande.",
        "low": "Los primeros segundos están flojos: lo principal aparece muy tarde o no se ve claro de entrada.",
    },
    "Retention": {
        "high": "A lo largo del cut hay frames o acciones nuevas, así que el interés no se cae.",
        "mid": "El interés no aguanta parejo: hay tramos sin nada nuevo por mucho tiempo.",
        "low": "Hay tramos sin acción ni imagen nueva, así que el cut se quiere saltar.",
    },
    "Pacing": {
        "high": "Los shots cambian a tiempo: ningún plano se queda más de lo necesario.",
        "mid": "El cambio de shots está, pero a veces un plano se queda un poco más de lo debido.",
        "low": "Los shots cambian muy tarde: un mismo plano se atora y el cut empieza a arrastrar.",
    },
    "Visual clarity": {
        "high": "El frame se lee fácil: un objeto principal o una acción jalan la atención de volada.",
        "mid": "A veces el frame trae demasiado: varios objetos, texto chico o un fondo cargado.",
        "low": "Hay demasiado en el frame: fondo, texto y detalles pelean y se pierde lo principal.",
    },
    "Visual punch": {
        "high": "La imagen está fuerte: el objeto se ve bien, el movimiento se lee, el contraste aguanta.",
        "mid": "La imagen está bien, pero a veces el objeto sale chico o falta contraste.",
        "low": "La imagen está floja: poco tamaño, poco movimiento o poco contraste para jalar el ojo.",
    },
}

_SIMPLIFIED_METRIC_SUMMARY_EN = {
    "Hook": {
        "high": "From the first shot it is clear what to watch: the main subject or action lands fast.",
        "mid": "The opening is okay, but the main subject could appear earlier and bigger.",
        "low": "The first seconds are weak: the main thing arrives too late or does not read clearly.",
    },
    "Retention": {
        "high": "The cut keeps introducing new frames or actions, so attention does not drop.",
        "mid": "Attention slips in places — some sections sit too long without anything new.",
        "low": "There are sections with no new action or visual, so the cut feels skippable.",
    },
    "Pacing": {
        "high": "Shots change at the right time — no plane sits longer than it needs to.",
        "mid": "The shot changes are there, but a few hang slightly longer than they should.",
        "low": "Shots change too late — the same plane stalls and the cut starts to drag.",
    },
    "Visual clarity": {
        "high": "The frame reads easily: a single main subject or action takes attention quickly.",
        "mid": "The frame is sometimes crowded: extra objects, tiny text, or a noisy background.",
        "low": "Too many elements compete in the frame — the main point gets lost.",
    },
    "Visual punch": {
        "high": "The visual is strong: subject is clear, motion reads, contrast holds.",
        "mid": "The visual is fine, but the subject is sometimes small or contrast is weak.",
        "low": "The visual is weak — not enough scale, motion, or contrast to pull the eye.",
    },
}


def _simplify_metrics(review: dict[str, Any], language: str = "es") -> None:
    metrics = review.get("metrics")
    if not isinstance(metrics, list):
        return

    summary_map = _SIMPLIFIED_METRIC_SUMMARY_EN if language == "en" else _SIMPLIFIED_METRIC_SUMMARY_ES

    for item in metrics:
        if not isinstance(item, dict):
            continue
        metric_key = str(item.get("key") or "")
        simple_label = _SIMPLIFIED_METRIC_LABELS_EN_JARGON.get(metric_key) or str(item.get("label") or "")
        item["label"] = simple_label
        score = int(item.get("score") or 0)
        bucket = "high" if score >= 75 else "mid" if score >= 60 else "low"
        item["summary"] = summary_map.get(simple_label, {}).get(bucket, item.get("summary", ""))


# Focus-window labels follow the engine-side ES wording (Tramo fuerte / Bache /
# Cambio brusco) when language=es, English equivalents when language=en. The
# title_map below normalises a few legacy / mojibake-corrupted titles to the
# canonical ES form first; the EN dispatch then translates from ES.
_FOCUS_WINDOW_TITLE_NORMALISE = {
    "Tramo fuerte": "Tramo fuerte",
    "Bache": "Bache",
    "Cambio brusco": "Cambio brusco",
    # Legacy English aliases (LLM occasionally emits these).
    "Strong section": "Tramo fuerte",
    "Where to fix first": "Bache",
    "Where to speed up": "Cambio brusco",
}

_FOCUS_WINDOW_TITLE_EN = {
    "Tramo fuerte": "Strong section",
    "Bache": "Where to fix first",
    "Cambio brusco": "Where to speed up",
}

_FOCUS_WINDOW_SUMMARY_ES = {
    "Tramo fuerte": "Aquí el cut se ve más fuerte que en el resto.",
    "Bache": "Empieza los ajustes por aquí.",
    "Cambio brusco": "Aquí conviene acortar el tramo o brincar más rápido al siguiente beat.",
}

_FOCUS_WINDOW_SUMMARY_EN = {
    "Tramo fuerte": "This is where the cut looks strongest.",
    "Bache": "Start the edits here.",
    "Cambio brusco": "Trim this stretch or jump faster to the next beat.",
}


def _simplify_focus_windows(review: dict[str, Any], language: str = "es") -> None:
    windows = review.get("focus_windows")
    if not isinstance(windows, list):
        return

    summary_map = _FOCUS_WINDOW_SUMMARY_EN if language == "en" else _FOCUS_WINDOW_SUMMARY_ES
    label_translator = _FOCUS_WINDOW_TITLE_EN if language == "en" else None

    for item in windows:
        if not isinstance(item, dict):
            continue
        original_title = str(item.get("label") or "")
        canonical = _FOCUS_WINDOW_TITLE_NORMALISE.get(original_title, original_title)
        if label_translator is not None:
            item["label"] = label_translator.get(canonical, canonical)
        else:
            item["label"] = canonical
        if canonical in summary_map:
            item["summary"] = summary_map[canonical]


# Action-item normalisation: pull legacy RU titles to canonical ES, translate
# to EN when needed. The instruction rewrites strip TRIBE-specific jargon and
# drop "Why:" prefixes regardless of language.
_ACTION_ITEM_TITLE_NORMALISE = {
    "Arreglar este tramo": "Arreglar este tramo",
    "Dejar como está": "Dejar como está",
    "Revisar este tramo": "Revisar este tramo",
    "Decir lo principal antes": "Decir lo principal antes",
}

_ACTION_ITEM_TITLE_EN = {
    "Arreglar este tramo": "Fix this section",
    "Dejar como está": "Keep as is",
    "Revisar este tramo": "Check this section",
    "Decir lo principal antes": "Say the key line earlier",
}

# Instruction rewrites: language-agnostic brand + "Why:" prefix strips.
# Post-S2 the LLM writes ES, so the legacy RU substring rewrites are gone.
_ACTION_ITEM_INSTRUCTION_REWRITES = (
    ("TRIBE", ""),
    ("Why:", ""),
    ("Por qué:", ""),
    ("Почему:", ""),
)


def _simplify_action_items(review: dict[str, Any], language: str = "es") -> None:
    items = review.get("action_items")
    if not isinstance(items, list):
        return

    title_translator = _ACTION_ITEM_TITLE_EN if language == "en" else None

    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        canonical = _ACTION_ITEM_TITLE_NORMALISE.get(title, title)
        if title_translator is not None:
            item["title"] = title_translator.get(canonical, canonical)
        else:
            item["title"] = canonical
        instruction = " ".join(str(item.get("instruction") or "").split())
        for old, new in _ACTION_ITEM_INSTRUCTION_REWRITES:
            instruction = instruction.replace(old, new)
        item["instruction"] = instruction.strip(" -,:")
        item["why"] = ""


_SPEECH_NOTE_AVAILABLE = {
    "es": "Aquí va el texto de voz del cut. Sirve para checar qué palabras sonaron y dónde.",
    "en": "Here is the speech transcript for the cut. Use it to see which words landed and where.",
}
_SPEECH_NOTE_UNAVAILABLE = {
    "es": "La voz en este cut se reconoció con poca confianza. Mira frame, ritmo y cambios de escena primero.",
    "en": "Speech recognition for this cut was low-confidence. Read frame, pacing, and scene changes first.",
}
_SPEECH_MESSAGE_UNAVAILABLE = {
    "es": "La voz en este cut se reconoció con poca confianza.",
    "en": "Speech recognition for this cut was low-confidence.",
}

# Speech-metric labels follow the engine-side ES wording (Entrada de voz,
# Palabras por segundo, …); the EN dispatch translates them.
_SPEECH_LABEL_NORMALISE = {
    "Entrada de voz": "Entrada de voz",
    "Palabras por segundo": "Palabras por segundo",
    "Densidad del texto": "Densidad del texto",
    "Pausas largas": "Pausas largas",
    "Confianza del ASR": "Confianza del ASR",
}

_SPEECH_LABEL_EN = {
    "Entrada de voz": "Voice entry",
    "Palabras por segundo": "Words per second",
    "Densidad del texto": "Speech density",
    "Pausas largas": "Long pauses",
    "Confianza del ASR": "ASR confidence",
}


def _simplify_speech(review: dict[str, Any], language: str = "es") -> None:
    speech = review.get("speech")
    if not isinstance(speech, dict):
        return
    if speech.get("available"):
        speech["note"] = _SPEECH_NOTE_AVAILABLE.get(language, _SPEECH_NOTE_AVAILABLE["es"])
    else:
        speech["note"] = _SPEECH_NOTE_UNAVAILABLE.get(language, _SPEECH_NOTE_UNAVAILABLE["es"])
        speech["message"] = _SPEECH_MESSAGE_UNAVAILABLE.get(language, _SPEECH_MESSAGE_UNAVAILABLE["es"])

    metrics = speech.get("metrics")
    if not isinstance(metrics, list):
        return

    label_translator = _SPEECH_LABEL_EN if language == "en" else None

    for item in metrics:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "")
        canonical = _SPEECH_LABEL_NORMALISE.get(label, label)
        if label_translator is not None:
            item["label"] = label_translator.get(canonical, canonical)
        else:
            item["label"] = canonical


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
    titles = ("Hacer primero", "Hacer después", "Revisar después")
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
        return "Qué hacer"
    compact = " ".join(words[:4])
    return compact[:42].rstrip(" -,:.")


def _clean_sentence(value: str) -> str:
    text = " ".join(str(value).strip().split())
    # Brand + explanation-prefix strips. Post-S2 the LLM is prompted in ES
    # so the legacy RU-specific bans are gone. We keep ``TRIBE`` (brand)
    # and the EN/ES/RU "Why:" prefixes the model occasionally drops in.
    banned = (
        "TRIBE",
        "Why:",
        "Why",
        "Por qué:",
        "Por qué",
        "Почему:",
        "Почему",
    )
    for token in banned:
        text = text.replace(token, "")
    return " ".join(text.split()).strip(" -,:")


def _sanitize_generated_copy(review: dict[str, Any]) -> None:
    """Strip brand + explanation-prefix tokens from every LLM-produced field.

    Post-S2 the LLM is prompted in ES; the legacy RU regex-rewrite block
    that lived here is dead and was removed. ``_clean_sentence`` is
    language-agnostic and handles the brand / "Why:" prefix scrub for both
    languages.
    """

    for key in ("verdict", "executive_summary", "product_summary"):
        value = review.get(key)
        if isinstance(value, str) and value.strip():
            review[key] = _clean_sentence(value)

    for key in ("strengths", "weaknesses"):
        items = review.get(key)
        if isinstance(items, list):
            review[key] = [_clean_sentence(item) for item in items if isinstance(item, str) and _clean_sentence(item)]

    plan = review.get("recommendation_plan")
    if isinstance(plan, list):
        cleaned_plan: list[dict[str, str]] = []
        for item in plan:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            detail = _clean_sentence(str(item.get("detail") or ""))
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
            title = _clean_sentence(str(item.get("title") or ""))
            instruction = _clean_sentence(str(item.get("instruction") or ""))
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
