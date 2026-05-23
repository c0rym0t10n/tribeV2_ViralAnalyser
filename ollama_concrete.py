"""Strict-fallback copy builders for the simplified-review flow.

Lifted out of :mod:`ollama_runtime` in Stage-2 / G4 and translated to
Spanish (Mexican coloquial) in Stage-3 / S2. When the local Ollama server
is unreachable (or returns no parseable structured reply), the runtime
calls :func:`_build_strict_simple_copy` to assemble a deterministic ES
review from a hand-written copy library + the metric scores already on
the review dict.

The action library + variant tables stay parallel to ``ACTION_VARIANTS_ES``
in :mod:`report_localization`; consolidating both halves into a single
table is a follow-up cleanup, out of scope for S2.
"""

from __future__ import annotations

from typing import Any

from ollama_sanitize import _clean_sentence


# Canonical "keep" action title used as a sentinel by the plan / weakness
# builders to filter the no-edit row out of the action-item list. The LLM
# also outputs this title verbatim when it decides the strongest section
# does not need an edit, so we keep one source of truth.
KEEP_AS_IS_TITLE = "Dejar como está"


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
            "title": "Muestra lo principal antes",
            "instruction": "Muestra lo principal desde el primer shot, tumba el setup largo y mete la frase clave antes.",
            "keep": "Deja este arranque como referencia. Aquí ya se entiende de volada qué está pasando.",
            "focus_label": "Dónde reforzar el arranque",
            "focus_summary": "Muestra lo principal antes y tumba el setup largo.",
        },
        "sustain": {
            "title": "Acorta el tramo arrastrado",
            "instruction": "Tumba 1-2 segundos antes de este punto o brinca más rápido al siguiente beat.",
            "keep": "Deja este tramo como referencia. Aquí el ritmo ya jala.",
            "focus_label": "Dónde acortar",
            "focus_summary": "Acorta el tramo arrastrado o brinca más rápido al siguiente beat.",
        },
        "transition": {
            "title": "Cambia el shot antes",
            "instruction": "Cambia el plano, ángulo o acción más temprano para que este tramo no arrastre.",
            "keep": "Deja el ritmo actual como referencia. Aquí el tramo ya no arrastra.",
            "focus_label": "Dónde apurar",
            "focus_summary": "Aquí conviene cambiar el plano antes o meter un acento visual nuevo.",
        },
        "stability": {
            "title": "Haz lo principal más visible",
            "instruction": "Haz lo principal más visible: objeto más grande, fondo más limpio o menos detalles que compiten.",
            "keep": "Deja este tramo como referencia. Aquí lo principal se lee mejor.",
            "focus_label": "Dónde resaltar lo principal",
            "focus_summary": "Aquí conviene resaltar más lo principal y tumbar los detalles extra.",
        },
        "density": {
            "title": "Muestra el producto más grande",
            "instruction": "Muestra el objeto más grande, mete movimiento en el frame o sube el contraste.",
            "keep": "Deja la escala y el contraste actuales. Este tramo se ve más fuerte que el resto.",
            "focus_label": "Dónde reforzar la imagen",
            "focus_summary": "Muestra el objeto más grande o mete una acción más visible.",
        },
        "speech_start": {
            "title": "Di lo principal antes",
            "instruction": "Mete la frase clave antes de este punto o tumba la entrada muda.",
            "keep": "",
            "focus_label": "Dónde meter la frase antes",
            "focus_summary": "Mete la frase clave antes y tumba la entrada muda.",
        },
        "pause": {
            "title": "Apura el tramo arrastrado",
            "instruction": "Acorta el tramo arrastrado y tumba el hueco vacío.",
            "keep": "",
            "focus_label": "Dónde apretar la entrega",
            "focus_summary": "Aquí conviene tumbar el hueco vacío y apretar la entrega.",
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
            {"title": "Muestra lo principal antes", "instruction": "Jala el frame principal o el oferta más cerca de este punto. Tumba el setup largo de adelante."},
            {"title": "Empieza con el resultado", "instruction": "Pon antes de este punto un frame donde se vea de volada qué se va a llevar el espectador."},
            {"title": "Tumba el setup", "instruction": "Si antes de este lugar hay introducción, recórtala y arranca más cerca de la acción."},
        ],
        "sustain": [
            {"title": "Acorta el tramo arrastrado", "instruction": "Tumba 1-2 segundos antes de este punto o brinca más rápido al siguiente beat."},
            {"title": "Mete un giro nuevo", "instruction": "Antes de este punto inserta un detalle nuevo, movimiento o cambio de plano para que el cut no se cuelgue."},
            {"title": "Aprieta el ritmo", "instruction": "Quítale la pausa y deja solo los frames que mueven la escena hacia adelante."},
        ],
        "transition": [
            {"title": "Cambia el shot antes", "instruction": "Cambia el plano, ángulo o acción más temprano para que este tramo no arrastre."},
            {"title": "Mete un acento visual", "instruction": "Antes de este punto mete movimiento, gesto, push-in o cambio de escala."},
            {"title": "Tumba el shot detenido", "instruction": "Si el frame se queda sin acción nueva, recórtalo hasta el primer movimiento claro."},
        ],
        "stability": [
            {"title": "Limpia el frame", "instruction": "Deja un objeto principal y tumba los detalles o textos extra a su alrededor."},
            {"title": "Endurece el foco", "instruction": "Resalta el objeto principal con tamaño, posición o un fondo más limpio."},
            {"title": "Descongestiona la composición", "instruction": "Tumba los elementos que compiten para que la mirada no se parta entre detalles."},
        ],
        "density": [
            {"title": "Muestra el producto más grande", "instruction": "Sube el objeto en escala, mete movimiento en el frame o sube el contraste."},
            {"title": "Endurece el visual punch", "instruction": "Antes de este punto mete un frame más brillante, un close-up o una acción más fuerte."},
            {"title": "Sube el contraste", "instruction": "Separa el objeto principal del fondo con luz, color o una composición más limpia."},
        ],
        "speech_start": [
            {"title": "Di lo principal antes", "instruction": "Mete la frase clave antes de este punto y tumba la entrada muda."},
            {"title": "Mueve la frase adelante", "instruction": "Pon la frase clave más cerca del arranque del tramo flojo."},
        ],
        "pause": [
            {"title": "Tumba la pausa", "instruction": "Recorta el hueco vacío o mete la frase más apretada para que el tramo no se caiga."},
            {"title": "Aprieta el habla", "instruction": "Comprime el espacio entre palabras y deja solo la frase que necesitas."},
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
        windows[0]["label"] = "Tramo fuerte"
        windows[0]["summary"] = _action_library(strongest)["keep"] or "Deja este tramo como referencia."
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
    keep_item = next((item for item in actions if isinstance(item, dict) and item.get("title") == KEEP_AS_IS_TITLE), None)
    edit_items = [
        item
        for item in actions
        if isinstance(item, dict) and item.get("title") != KEEP_AS_IS_TITLE
    ]

    plan: list[dict[str, str]] = []
    if keep_item:
        plan.append(
            {
                "title": "Dejar",
                "detail": f"{keep_item['timestamp']}: {_compact_instruction(str(keep_item.get('instruction') or ''))}",
            }
        )
    if edit_items:
        first = edit_items[0]
        plan.append(
            {
                "title": "Hacer primero",
                "detail": f"{first['timestamp']}: {_compact_instruction(str(first.get('instruction') or ''))}",
            }
        )
    if len(edit_items) > 1:
        second = edit_items[1]
        plan.append(
            {
                "title": "Hacer después",
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
            f"{best_window['timestamp']}: {_action_library(strongest)['keep'] or 'Deja este tramo como referencia.'}"
        )
    if strongest == "early_response":
        items.append("Conserva el arranque rápido. No estires la entrada con inserts nuevos.")
    elif strongest == "transition":
        items.append("Conserva el ritmo actual de cambio de shots en los tramos fuertes. Ya ayuda a que el cut no arrastre.")
    else:
        items.append("No le metas ajustes nuevos a los tramos fuertes. Tómalos de referencia para ritmo y entrega.")
    return items[:2]


def _build_concrete_weaknesses(review: dict[str, Any]) -> list[str]:
    actions = review.get("action_items")
    if not isinstance(actions, list):
        return []
    edit_items = [
        item
        for item in actions
        if isinstance(item, dict) and item.get("title") != KEEP_AS_IS_TITLE
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
            "Abajo van marcados los baches del cut y soluciones simples — qué exactamente cambiar.",
            "Mira los puntos marcados abajo y edita el cut un tramo a la vez.",
        )

    keep_item = next((item for item in actions if isinstance(item, dict) and item.get("title") == KEEP_AS_IS_TITLE), None)
    edit_items = [
        item
        for item in actions
        if isinstance(item, dict) and item.get("title") != KEEP_AS_IS_TITLE
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
        return "El cut está fuerte."
    if score >= 60:
        return "El cut está bien, pero le faltan ajustes."
    return "El cut está flojo."


def _simple_overview_text(metric_scores: dict[str, int], edit_count: int) -> str:
    early = metric_scores.get("early_response", 0)
    sustain = metric_scores.get("sustain", 0)
    transition = metric_scores.get("transition", 0)
    stability = metric_scores.get("stability", 0)
    density = metric_scores.get("density", 0)

    if early >= 75:
        start_phrase = "El arranque se siente firme"
    elif early >= 60:
        start_phrase = "El arranque está normal"
    else:
        start_phrase = "El arranque está flojo"

    if sustain < 60:
        middle_phrase = "después el ritmo se cae"
    elif transition < 60:
        middle_phrase = "después los shots cambian tarde"
    elif stability < 60:
        middle_phrase = "a veces el frame trae demasiado de un jalón"
    elif density < 60:
        middle_phrase = "a veces la imagen se ve floja"
    else:
        middle_phrase = "después el cut se mantiene parejo"

    tail = " Los baches están marcados abajo y al lado ya hay soluciones simples." if edit_count else " Abajo puedes ver los puntos marcados del cut."
    return f"{start_phrase}, pero {middle_phrase}.{tail}"


def _simple_banner_text(metric_scores: dict[str, int], has_keep_item: bool, edit_count: int) -> str:
    parts: list[str] = []
    if has_keep_item:
        parts.append("no le muevas a los tramos fuertes")
    if metric_scores.get("transition", 0) < 60:
        parts.append("los baches casi siempre se arreglan cambiando el shot antes")
    elif metric_scores.get("stability", 0) < 60:
        parts.append("los baches casi siempre se arreglan limpiando el frame")
    elif metric_scores.get("density", 0) < 60:
        parts.append("los baches casi siempre se arreglan con una imagen más fuerte")
    else:
        parts.append("los baches están marcados abajo")
    if edit_count:
        parts.append("abajo ya hay recomendaciones concretas de qué cambiar")
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
