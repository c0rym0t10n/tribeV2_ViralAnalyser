"""Multi-variant comparison logic and the comparison entrypoint.

Owns ``generate_comparison_report`` plus all the helpers that aggregate
per-variant numbers into a ranking, axis-winners list, common-gaps list,
comparison rows, and prose summaries. Reads from :mod:`tribe_review.copy_es`
for friendly metric labels and from :mod:`tribe_review.metrics` for the
templated-prose helper.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

import numpy as np

from analysis_settings import AnalysisModeProfile, get_analysis_mode_profile

from tribe_review.copy_es import _friendly_metric_label
from tribe_review.metrics import _pick_template


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
        "title": f"Comparativa de {len(ranked)} versiones",
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
        "signal_note": "La comparativa se mide en una sola curva para todas las versiones. Gana la que arranca más fuerte, mantiene mejor base y tiene menos bajones bruscos — no la del pico aislado.",
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
            "summary": f"En «{row['label'].lower()}» esta versión saca la diferencia más clara contra el resto.",
        }
        for row in comparison_rows[:4]
    ]


def _build_common_gaps(variants: list[dict[str, Any]], profile: AnalysisModeProfile) -> list[str]:
    gaps = []
    metric_keys = [str(metric.get("key") or "") for metric in variants[0].get("metrics", []) if isinstance(metric, dict)]
    for key in metric_keys:
        scores = [int(variant["metric_lookup"].get(key, 0)) for variant in variants]
        if scores and mean(scores) < profile.recommendation_cutoff:
            gaps.append(f"En todas las versiones flojea «{_friendly_metric_label(key).lower()}». Ni el líder da margen ahí — buen candidato para una prueba aparte.")
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
        (delta == 0 and early >= 65 and avg >= 60, f"Líder del A/B: arranca rápido y mantiene buena base. La fortaleza principal es «{strongest['label'].lower()}»."),
        (delta == 0 and floor < 35, f"Líder por score total, pero con riesgo: hay bajones profundos. Siguiente ajuste: «{weakest['label'].lower()}»."),
        (delta == 0, f"Líder del A/B. Esta versión gana por suma de métricas, no por un pico aislado; lo más fuerte es «{strongest['label'].lower()}»."),
        (delta <= 3 and early >= avg + 8, f"Casi líder gracias al arranque fuerte, pero la base no alcanza después. Revisa «{weakest['label'].lower()}»."),
        (delta <= 3, f"Casi pegado al líder: la diferencia es chica. En la siguiente prueba compara arranque y mitad, no picos aislados."),
        (delta <= 7 and avg >= 55, f"Versión competitiva por base, pero pierde con el líder en detalles. La reserva principal está en «{weakest['label'].lower()}»."),
        (early < 45, "La versión pierde el arranque: la curva sube tarde, así que ni los buenos momentos posteriores rescatan el total."),
        (floor < 30, f"El problema central son los bajones profundos. La fortaleza «{strongest['label'].lower()}» está, pero «{weakest['label'].lower()}» jala el resultado abajo."),
        (score >= 55, f"La versión tiene base que jala, pero el líder está más parejo. Amarra «{strongest['label'].lower()}» y revisa aparte «{weakest['label'].lower()}»."),
        (True, f"La versión queda claramente abajo del líder. Lo mejor es «{strongest['label'].lower()}», pero la curva total está demasiado dispareja."),
    ]
    return _pick_template(candidates, "")


def _build_compare_verdict(best: dict[str, Any], runner_up: dict[str, Any], variant_count: int) -> str:
    delta = _comparison_score_value(best) - _comparison_score_value(runner_up)
    best_avg = _comparison_value(best, "comparison_signal_avg", _comparison_score_value(best))
    best_early = _comparison_value(best, "comparison_early_avg", best_avg)
    runner_avg = _comparison_value(runner_up, "comparison_signal_avg", _comparison_score_value(runner_up))
    window = best.get("comparison_window_seconds")
    window_line = f" La comparativa corre en una ventana común hasta los {window}s; los últimos 5 segundos quedan fuera." if window else ""
    candidates = [
        (delta >= 12 and best_early >= 65, f"De las {variant_count} versiones, la que más claro lidera es «{best['title']}»: arranca rápido y mantiene la diferencia por base.{window_line}"),
        (delta >= 12, f"«{best['title']}» va claramente adelante en el score de comparación. La razón es base más alta, no un pico aislado.{window_line}"),
        (delta >= 7 and runner_avg >= best_avg - 5, f"«{best['title']}» va al frente, pero «{runner_up['title']}» queda como control cercano. Vale revalidarlo con otro A/B, sobre todo en arranque y mitad.{window_line}"),
        (delta >= 7, f"«{best['title']}» se ve como el primer candidato para la siguiente prueba: la parte buena de la curva es más fuerte y los baches pesan menos.{window_line}"),
        (delta <= 3 and best_early < runner_avg, f"El liderazgo de «{best['title']}» es mínimo. No es la ganadora final — vale volverla a probar contra «{runner_up['title']}».{window_line}"),
        (delta <= 3, f"La diferencia entre «{best['title']}» y «{runner_up['title']}» es chica. Mejor decidir después de otra corrida con un ajuste puntual.{window_line}"),
        (best_early >= 70 and best_avg < 55, f"«{best['title']}» gana por arranque fuerte, pero la base todavía no da margen. Hay que revisar la mitad del video.{window_line}"),
        (best_avg >= 65, f"«{best['title']}» lidera por base más alta de la curva. Es más confiable que ganar por un solo pico tardío.{window_line}"),
        (best_avg < 50, f"Ni el líder «{best['title']}» se ve sólido todavía. La comparativa marca la mejor entre las actuales, no la versión final.{window_line}"),
        (True, f"Ahorita el primer candidato es «{best['title']}»; deja «{runner_up['title']}» como control cercano para el siguiente A/B.{window_line}"),
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
        (delta >= 12 and best_early >= 65, f"Mejor candidato: «{best['title']}» — arranque {best_early}, base {best_avg}. Saca {delta} puntos a «{runner_up['title']}», así que tiene sentido tomarla como base."),
        (delta >= 12, f"«{best['title']}» va adelante por {delta} puntos. Lo que pesa no es el pico — es la base {best_avg} contra {runner_avg} de la versión más cercana."),
        (delta <= 3, f"«{best['title']}» va adelante apenas por {delta} puntos. Es una carrera pegada: deja «{runner_up['title']}» en el control y compara otra vez después de un ajuste puntual."),
        (best_early < 50, f"El líder se eligió por suma de la curva, pero el arranque no es ideal: {best_early}. La siguiente prueba debe reforzar los primeros segundos, no solo la mitad."),
        (best_avg < 50, f"Ni la mejor versión da una base alta todavía. «{best['title']}» gana el set actual, pero todo el paquete necesita refuerzo."),
        (top_axis == "arranque de la curva", f"La diferencia se ve mejor en el arranque: «{best['title']}» sube la curva más rápido y por eso pasa a «{runner_up['title']}»."),
        (top_axis == "fuerza visual", f"La ventaja clave del líder es la base. «{best['title']}» se ve más útil como punto de partida porque no depende solo de picos aislados."),
        (top_axis == "bajones bruscos", f"El líder gana porque cae menos entre los tramos fuertes. En la siguiente versión hay que conservar esa parejidad."),
        (top_axis == "ritmo del cambio", f"La diferencia central del líder es el ritmo. Da más seguido un motivo nuevo para seguir viendo."),
        (True, f"«{best['title']}» es el primer candidato, «{runner_up['title']}» queda de control. Comparen arranque, base y baches, no solo el pico más alto."),
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
        (delta >= 10 and best_floor >= 45, f"Para la siguiente prueba toma «{best['title']}» como versión principal: gana no solo por el pico, también por una curva más estable sin bajones profundos."),
        (delta >= 10, f"«{best['title']}» le gana al set actual, pero los baches siguen ahí. Antes de escalar, revisa aparte «{weakest}»."),
        (delta <= 3, f"No declares ganador final. «{best['title']}» y «{runner_up['title']}» están pegadas — la siguiente prueba debe mover un solo elemento concreto."),
        (best_avg < 50, f"Ni el líder está sólido en base todavía. No se trata de elegir ganador — hay que subir la base de todas las versiones."),
        (bool(gap_line), f"Toma «{best['title']}» como primera base, pero el riesgo común es igual para todas: {gap_line}"),
        (_variant_metric(runner_up, "max")["key"] == _variant_metric(best, "min")["key"], f"«{runner_up['title']}» trae una pista útil sobre el bache del líder. Mira cómo resuelve «{weakest}» y pasa la técnica a «{best['title']}»."),
        (_comparison_value(best, "comparison_early_avg", 0) < 55, f"Hay liderazgo, pero el arranque puede subir. La siguiente iteración de «{best['title']}» debe mostrar el objeto principal o el resultado más rápido."),
        (_comparison_value(best, "comparison_floor", 0) < 35, f"La tarea principal es quitar los bajones profundos del líder. No metas efectos nuevos hasta que los baches se vean más claros."),
        (delta >= 5, f"Puedes llevar «{best['title']}» de primera y dejar «{runner_up['title']}» como versión de control para validar el siguiente ajuste."),
        (True, f"Siguiente paso: A/B entre «{best['title']}» y «{runner_up['title']}». Comparen cuál aguanta mejor arranque, mitad y baches."),
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
        (True, f"En la siguiente prueba lleva «{best['title']}» como base: ahorita tiene el mejor score en la ventana común."),
        (delta <= 3, f"La ventaja es chica. No saques conclusión de una sola corrida: compara «{best['title']}» y «{runner_up['title']}» otra vez después de un ajuste puntual."),
        (delta >= 8, f"Conserva «{strongest}» del líder sin cambios extra. Es la técnica principal que está dando la diferencia."),
        (best_early < 55, "El líder tiene margen en los primeros segundos. Prueba mostrar el objeto principal, el resultado o el conflicto antes."),
        (best_avg < 55, "La base del líder no está lo bastante alta. No es un solo pico — hay que ajustar varios frames promedio entre los buenos momentos."),
        (best_floor < 35, f"El líder tiene bajones profundos. Empieza por «{weakest}» y compara los baches con los tramos fuertes vecinos."),
        (runner_avg >= best_avg - 5, f"Deja «{runner_up['title']}» como control cercano: en base está pegado al líder y puede mostrar qué pasar a la versión principal."),
        (bool(common_gaps), common_gaps[0] if common_gaps else ""),
        (_comparison_value(runner_up, "comparison_early_avg", 0) > best_early + 5, f"«{runner_up['title']}» tiene mejor arranque que el líder. Revisa si puedes pasar su primer frame o entrada a «{best['title']}»."),
        (True, "No uses los últimos 5 segundos como argumento principal. Mira arranque, mitad y bajones en la ventana común."),
    ]
    recs: list[str] = []
    for condition, text in candidates:
        if condition and text and text not in recs:
            recs.append(text)
        if len(recs) >= 4:
            break
    return recs[:4]
