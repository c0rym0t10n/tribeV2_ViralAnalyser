"""Verdict, executive / product summaries, recommendations, and action items.

Owns all the prose-level outputs of a single-variant review: strengths,
weaknesses, the verdict line, the executive + product summaries, the long
recommendation list, the recommendation plan, and the action-item builder.
Pulls labels and copy from :mod:`tribe_review.copy_es`, score helpers from
:mod:`tribe_review.metrics`, and timeline-shape helpers from
:mod:`tribe_review.timeline`.
"""

from __future__ import annotations

from typing import Any

from analysis_settings import AnalysisModeProfile, get_analysis_mode_profile

from tribe_review.copy_es import (
    ACTION_VARIANTS,
    _friendly_metric_label,
    _simple_metric_action,
)
from tribe_review.metrics import (
    ReviewMetric,
    _metric_display,
    _metric_scores,
    _pick_template,
)
from tribe_review.timeline import (
    _drop_timestamps,
    _speech_line,
)


def _build_strengths(metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    del profile
    strengths = [
        f"Lo más fuerte ahorita es «{_metric_display(metrics[0])}»: {metrics[0].summary.lower()}",
        f"Segunda referencia útil — «{_metric_display(metrics[1])}»: {metrics[1].summary.lower()}",
    ]
    if speech_layer.get("available"):
        strengths.append("Whisper reconoció voz; los tramos fuertes los cruzas con frases y entrega específicas.")
    else:
        strengths.append("Sin voz confiable, los tramos fuertes se revisan por imagen, ritmo y audio.")
    return strengths


def _build_weaknesses(metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> list[str]:
    del profile
    items = [
        f"El bache principal está en «{_metric_display(metrics[-1])}»: {metrics[-1].summary.lower()}",
        f"Sigue con «{_metric_display(metrics[-2])}»: ahí está el siguiente margen claro para mover.",
    ]
    if speech_layer.get("available") and isinstance(speech_layer.get("speech_start_seconds"), float) and speech_layer["speech_start_seconds"] > 2.0:
        items.append("La voz entra tarde — los primeros segundos se aguantan en imagen y acción, sin apoyarse en palabras.")
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
        f"La voz entra cerca de los {float(speech_start):.2f}s. Si el mensaje clave está en palabras, jala la frase principal hacia el arranque."
        if speech_start_is_late
        else ""
    )
    pause_ratio = speech.get("pause_ratio")
    pause_ratio_is_high = isinstance(pause_ratio, (int, float)) and float(pause_ratio) > 0.28

    candidates = [
        (scores.get("early_response", 0) < cutoff, "El arranque sube de nivel tarde. Revisa el primer shot: lo principal debe aparecer antes, más grande, o con un resultado más claro."),
        (scores.get("sustain", 0) < cutoff, "Después de los picos la curva se cae rápido. Antes del bache mete un giro nuevo, cambio de plano, o acorta el tramo que no mueve la escena."),
        (scores.get("transition", 0) < cutoff, "El ritmo está flojo: el frame se queda en un mismo estado demasiado tiempo. Mete cambio de shot, gesto, acción o un caption corto antes."),
        (scores.get("stability", 0) < cutoff, "Hay bajones bruscos. Compara los baches con los tramos fuertes vecinos y tumba detalles que están diluyendo el foco principal."),
        (scores.get("density", 0) < cutoff, "La base está abajo de los picos. Sube la base del video: objeto principal más grande, fondo más limpio, movimiento más claro o más contraste."),
        (bool(drops), f"Empieza por revisar las ventanas {drops}: ahí la curva se cae respecto a los puntos vecinos. Checa qué cambia en frame, caption y ritmo en esos segundos."),
        (bool(speech.get("available")) and speech_start_is_late, speech_start_text),
        (bool(speech.get("available")) and pause_ratio_is_high, "Hay muchos huecos en la voz. Acorta las pausas o haz la entrega más densa, sobre todo cerca de los baches de la curva."),
        (not speech.get("available"), "Si las palabras pesan en el mensaje, revisa volumen, ruido y dicción: ahorita la capa de voz no da apoyo confiable para el análisis."),
        (duration_seconds > 30, "Después del ajuste principal, prueba una versión corta. Así se ve si la curva mejora con el recorte o si se pierde contexto importante."),
        (scores.get("early_response", 0) >= cutoff and scores.get("sustain", 0) < cutoff, "El arranque ya jala como referencia; el ajuste va por la mitad: ahí mete un motivo nuevo (info o visual) para seguir viendo."),
        (scores.get("density", 0) >= 75 and scores.get("stability", 0) < cutoff, "La imagen jala en promedio, pero hay bajones bruscos. No le metas a todo — suaviza los baches puntuales para no romper los frames fuertes."),
        (scores.get("transition", 0) >= 75 and scores.get("sustain", 0) < cutoff, "Eventos hay, pero la curva igual se cae. El problema no es solo la frecuencia de cambios — es qué tanto significado claro aportan los frames nuevos."),
        (scores.get("early_response", 0) < cutoff and scores.get("density", 0) >= 70, "El visual es fuerte, pero el arranque no alcanza a mostrarlo. Jala el frame grande más legible hacia los primeros segundos."),
        (scores[min_key] < 45 and scores[max_key] >= 70, f"La brecha entre lo fuerte y lo flojo está grande. No reescribas todo el video: amarra «{_friendly_metric_label(max_key).lower()}» y arregla aparte «{_friendly_metric_label(min_key).lower()}»."),
    ]

    recs: list[str] = []
    for condition, text in candidates:
        if condition and text not in recs:
            recs.append(text)
        if len(recs) >= 6:
            break
    if not recs:
        recs.append("No hay un problema grueso evidente en la curva. La siguiente prueba va de A/B: mueve un elemento a la vez y compara arranque, base y baches.")
    return recs[:6]


def _build_simple_recommendations(metrics: list[ReviewMetric], drop_moments: list[dict[str, Any]], duration_seconds: float, speech: dict[str, Any]) -> list[str]:
    profile = get_analysis_mode_profile("simplified")
    return _build_recommendations(metrics, drop_moments, duration_seconds, speech, profile)


def _build_recommendation_plan(recommendations: list[str], top_metric: ReviewMetric, weak_metric: ReviewMetric, profile: AnalysisModeProfile) -> list[dict[str, str]]:
    del profile
    return [
        {"title": "Qué dejar", "detail": f"No le muevas a la parte fuerte «{_metric_display(top_metric)}»: ya le está dando base al video."},
        {"title": "Qué revisar primero", "detail": recommendations[0] if recommendations else _simple_metric_action(weak_metric)},
        {"title": "Cómo revalidar", "detail": "Después del ajuste, compara la versión vieja con la nueva en la curva: arranque, base y bajones bruscos deben mejorar."},
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
        (overall_score >= 78 and scores.get(metrics[-1].key, 0) >= 65, f"El video está fuerte y bastante parejo. La base es «{strongest}»; los ajustes finos van por «{weakest}»."),
        (overall_score >= 75 and scores.get(metrics[-1].key, 0) < 60, f"El video tiene base fuerte, pero no aguanta parejo. Amarra «{strongest}» y empieza revisando «{weakest}»."),
        (early < 60 and density >= 65, "El problema no está en la imagen sino en qué tan rápido la entrega el arranque. Mete el visual fuerte más pronto."),
        (early < 60, f"El video sube de nivel muy despacio. Prioridad uno: el arranque; después «{weakest}»."),
        (sustain < 60 and early >= 65, "El arranque jala mejor que la mitad. No le muevas al inicio; mete un giro nuevo antes del primer bache visible."),
        (transition < 60, "La curva se cae por falta de eventos nuevos. Los tramos sin cambio de shot o acción hay que apretarlos antes."),
        (stability < 60, "El riesgo grande son los bajones bruscos. Puede haber frames buenos, pero los baches entre ellos jalan el resultado abajo."),
        (density < 60 and overall_score < 55, "Por ahora el video se aguanta en momentos puntuales. Hay que subir la base, no solo buscar un pico brillante."),
        (overall_score >= 60, f"La versión jala, pero está dispareja. Lo más fuerte es «{strongest}»; el margen principal está en «{weakest}»."),
        (overall_score < 60, f"Esto es más un borrador. Primero refuerza «{weakest}», luego revisa todo el video con un A/B."),
    ]
    return _pick_template(candidates, f"Referencia principal: «{strongest}». El ajuste fuerte está en «{weakest}».")


def _build_executive_summary(overall_score: int, top_metric: ReviewMetric, weak_metric: ReviewMetric, runner_metric: ReviewMetric, speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> str:
    del profile
    scores = {top_metric.key: top_metric.score, weak_metric.key: weak_metric.score, runner_metric.key: runner_metric.score}
    top = _metric_display(top_metric)
    runner = _metric_display(runner_metric)
    weak = _metric_display(weak_metric)
    speech = _speech_line(speech_layer)
    candidates = [
        (overall_score >= 80, f"Versión fuerte: la curva se mantiene alta y «{top}» da la base. Los ajustes van puntuales por «{weak}». {speech}"),
        (overall_score >= 72 and weak_metric.score < 60, f"El nivel general está bien, pero «{weak}» está limitando el total. Revisa los baches sin tocar lo que ya jala en «{top}». {speech}"),
        (weak_metric.key == "early_response", f"El tema central es el arranque: el video sube de nivel tarde. Amarra «{top}», pero jala el frame o el mensaje más legible hacia los primeros segundos. {speech}"),
        (weak_metric.key == "sustain", f"El arranque y algunos frames jalan mejor que la continuación. Hay que ver dónde empieza a caerse la curva y meter un giro nuevo ahí. {speech}"),
        (weak_metric.key == "transition", f"Al video le faltan eventos nuevos en los momentos clave. Amarra «{top}» y revisa el montaje en busca de shots que se alargan. {speech}"),
        (weak_metric.key == "stability", f"El problema central son los bajones bruscos entre tramos fuertes. Revisa los baches por detalles extra, pausas o pérdida de foco. {speech}"),
        (weak_metric.key == "density", f"Los mejores tramos están claramente arriba del promedio. No se trata de meter otro pico — hay que subir la base de la mayoría de los frames. {speech}"),
        (scores.get(top_metric.key, 0) - scores.get(weak_metric.key, 0) >= 25, f"La brecha entre lo fuerte y lo flojo está grande: tocar «{top}» es riesgoso, y «{weak}» da el margen de mejora más claro. {speech}"),
        (overall_score >= 60, f"La versión ya jala, pero requiere ajustes finos. Referencia: «{top}»; segunda fortaleza: «{runner}»; arreglo principal: «{weak}». {speech}"),
        (overall_score < 60, f"Por ahora es una versión interna en desarrollo. No empieces rehaciendo todo: arranca por una sola métrica floja: «{weak}». {speech}"),
    ]
    return _pick_template(candidates, f"Lo fuerte está en «{top}»; lo flojo, en «{weak}». Siguiente paso: un solo ajuste y comparar la curva otra vez.")


def _build_product_summary(overall_score: int, ordered_metrics: list[ReviewMetric], speech_layer: dict[str, Any], profile: AnalysisModeProfile) -> str:
    del profile
    scores = _metric_scores(ordered_metrics)
    strongest = _metric_display(ordered_metrics[0])
    weakest = _metric_display(ordered_metrics[-1])
    speech = _speech_line(speech_layer)
    candidates = [
        (overall_score >= 80, f"Puedes tomar esta versión como base de la siguiente prueba. Ya mantiene la curva alta; limita los ajustes a la zona de «{weakest}». {speech}"),
        (overall_score >= 70 and scores.get("early_response", 0) >= 70, f"El arranque ya jala — déjalo. La siguiente prueba va alrededor de cómo aguanta el video después de los primeros segundos. {speech}"),
        (scores.get("early_response", 0) < 60, f"Para el producto, ahorita lo más importante es explicar el valor más rápido. Jala el resultado, producto o conflicto hacia el inicio. {speech}"),
        (scores.get("sustain", 0) < 60, f"La versión pierde ritmo después de los buenos momentos. Mete en la mitad un paso nuevo de significado: acción, reacción, detalle o payoff. {speech}"),
        (scores.get("transition", 0) < 60, f"El montaje se siente alargado. La siguiente versión debe cambiar el estado del frame más seguido, sin caer en cuts caóticos. {speech}"),
        (scores.get("stability", 0) < 60, f"Los baches se sienten como pérdida de foco. En la siguiente versión, haz el objeto principal y la acción más legibles. {speech}"),
        (scores.get("density", 0) < 60, f"Al video le falta base: hay buenos momentos puntuales, pero la imagen base tiene que estar más fuerte. {speech}"),
        (overall_score >= 60, f"La base ya jala. No reescribas todo el video: amarra «{strongest}» y prueba un solo ajuste en la zona de «{weakest}». {speech}"),
        (overall_score < 50, f"Ahorita conviene más una iteración nueva alrededor de la métrica floja «{weakest}» que un pulido fino. {speech}"),
        (True, f"En la siguiente corrida mueve un solo elemento a la vez y ve qué pasa con el arranque, la base y los baches. {speech}"),
    ]
    return _pick_template(candidates, f"Lo más fuerte es «{strongest}»; lo más flojo, «{weakest}».")


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
