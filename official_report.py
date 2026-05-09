from __future__ import annotations

from pathlib import Path
from typing import Any

import moviepy as mpy
import numpy as np

from tribe_runtime import TribeRunResult


def generate_official_report(
    video_path: str | Path,
    run: TribeRunResult,
    variant_name: str | None = None,
) -> dict[str, Any]:
    preds = np.asarray(run.preds, dtype=float)
    if preds.ndim != 2 or preds.shape[0] < 1 or preds.shape[1] < 1:
        raise ValueError("TRIBE returned no usable predictions.")

    info = _read_video_info(video_path)
    info["title"] = variant_name or Path(video_path).stem

    timeline_seconds = _build_time_axis(preds.shape[0], run.timestamps)
    response_magnitude = np.mean(np.abs(preds), axis=1)
    display_score = _normalize_series(response_magnitude)
    timeline = _build_timeline(timeline_seconds, response_magnitude, display_score)
    simple_readout = _build_simple_readout(timeline_seconds, display_score)

    peak_index = int(np.argmax(response_magnitude))
    min_index = int(np.argmin(response_magnitude))

    return {
        "workflow": "official_tribe_v2",
        "mode": "single",
        "title": info["title"],
        "variant_name": info["title"],
        "variant_key": "v1",
        "video": info,
        "device": run.device,
        "modalities": run.modalities,
        "simple_readout": simple_readout,
        "practical_readout": _build_practical_readout(
            phase_states=_build_phase_states(display_score),
            strong_windows=_pick_windows(timeline_seconds, display_score, prefer="high"),
            weak_windows=_pick_windows(timeline_seconds, display_score, prefer="low"),
            modalities=run.modalities,
        ),
        "predictions": {
            "timesteps": int(preds.shape[0]),
            "vertices": int(preds.shape[1]),
            "shape": [int(preds.shape[0]), int(preds.shape[1])],
            "events_count": int(run.events_count),
            "mesh_level": run.mesh_level,
            "subject_model": run.subject_model,
            "hemodynamic_lag_seconds": float(run.hemodynamic_lag_seconds),
            "mean_response": round(float(np.mean(response_magnitude)), 5),
            "peak_response": round(float(np.max(response_magnitude)), 5),
            "peak_time_seconds": round(float(timeline_seconds[peak_index]), 2),
            "peak_time": _format_ts(timeline_seconds[peak_index]),
            "minimum_time_seconds": round(float(timeline_seconds[min_index]), 2),
            "minimum_time": _format_ts(timeline_seconds[min_index]),
        },
        "timeline": timeline,
        "official_sources": {
            "github": "https://github.com/facebookresearch/tribev2",
            "huggingface": "https://huggingface.co/facebook/tribev2",
            "demo": "https://aidemos.atmeta.com/tribev2/",
        },
    }


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


def _build_time_axis(total_frames: int, timestamps: list[float]) -> np.ndarray:
    if timestamps and len(timestamps) == total_frames:
        out = np.asarray(timestamps, dtype=float)
    elif timestamps and len(timestamps) > 1:
        out = np.linspace(float(timestamps[0]), float(timestamps[-1]), num=total_frames)
    else:
        out = np.arange(total_frames, dtype=float)
    if out.size:
        out = out - out[0]
    return out


def _build_timeline(
    timestamps: np.ndarray,
    response_magnitude: np.ndarray,
    display_score: np.ndarray,
) -> dict[str, Any]:
    points = [
        {
            "seconds": round(float(ts), 2),
            "timestamp": _format_ts(ts),
            "response_magnitude": round(float(response_magnitude[index]), 5),
            "signal_score": round(float(display_score[index]), 1),
        }
        for index, ts in enumerate(timestamps)
    ]

    return {
        "points": points,
        "svg_points": _build_svg_points(display_score),
        "markers": [],
        "avg_score": round(float(np.mean(display_score)), 1),
        "max_score": round(float(np.max(display_score)), 1),
        "min_score": round(float(np.min(display_score)), 1),
    }


def _build_simple_readout(timestamps: np.ndarray, display_score: np.ndarray) -> dict[str, Any]:
    strong_windows = _pick_windows(timestamps, display_score, prefer="high")
    weak_windows = _pick_windows(timestamps, display_score, prefer="low")
    phase_states = _build_phase_states(display_score)
    strong_reference = strong_windows[0] if strong_windows else None
    weak_reference = weak_windows[0] if weak_windows else None

    return {
        "es": {
            "title": "Lectura sencilla",
            "summary_title": "Qué significa",
            "summary_body": _summary_text_es(phase_states),
            "keep_title": "Qué dejar como referencia",
            "keep_body": _keep_text_es(strong_reference),
            "check_title": "Qué revisar primero",
            "check_body": _check_text_es(weak_reference, strong_reference),
            "steps_title": "Cómo usar esto",
            "steps": _steps_text_es(weak_reference, strong_reference),
        },
        "en": {
            "title": "Plain-language readout",
            "summary_title": "What this means",
            "summary_body": _summary_text_en(phase_states),
            "keep_title": "What to keep as the reference",
            "keep_body": _keep_text_en(strong_reference),
            "check_title": "What to check first",
            "check_body": _check_text_en(weak_reference, strong_reference),
            "steps_title": "How to use it",
            "steps": _steps_text_en(weak_reference, strong_reference),
        },
    }


def _build_practical_readout(
    phase_states: dict[str, str],
    strong_windows: list[dict[str, Any]],
    weak_windows: list[dict[str, Any]],
    modalities: list[str],
) -> dict[str, Any]:
    strong_reference = strong_windows[0] if strong_windows else None
    weak_reference = weak_windows[0] if weak_windows else None
    secondary_weak = weak_windows[1] if len(weak_windows) > 1 else None

    return {
        "es": {
            "title": "Recomendaciones prácticas",
            "summary": _practical_summary_es(phase_states, weak_reference),
            "cards": _practical_cards_es(strong_reference, weak_reference, secondary_weak, modalities),
        },
        "en": {
            "title": "Practical recommendations",
            "summary": _practical_summary_en(phase_states, weak_reference),
            "cards": _practical_cards_en(strong_reference, weak_reference, secondary_weak, modalities),
        },
    }


def _format_ts(seconds: float) -> str:
    total = int(round(float(seconds)))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def _normalize_series(values: np.ndarray) -> np.ndarray:
    low = float(np.min(values))
    high = float(np.max(values))
    if high - low < 1e-6:
        return np.full_like(values, 50.0, dtype=float)
    return 100.0 * (values - low) / (high - low)


def _build_phase_states(display_score: np.ndarray) -> dict[str, str]:
    if not len(display_score):
        return {"opening": "steady", "middle": "steady", "ending": "steady"}

    baseline = float(np.mean(display_score))
    boundaries = np.array_split(display_score, 3)
    names = ("opening", "middle", "ending")
    out: dict[str, str] = {}
    for name, chunk in zip(names, boundaries, strict=False):
        if not len(chunk):
            out[name] = "steady"
            continue
        delta = float(np.mean(chunk)) - baseline
        if delta >= 8.0:
            out[name] = "stronger"
        elif delta <= -8.0:
            out[name] = "weaker"
        else:
            out[name] = "steady"
    return out


def _pick_windows(
    timestamps: np.ndarray,
    display_score: np.ndarray,
    prefer: str,
    count: int = 2,
) -> list[dict[str, Any]]:
    if not len(display_score):
        return []

    window_size = max(3, min(8, len(display_score) // 8 or 3))
    scored_windows: list[tuple[float, int, int, int]] = []
    for center in range(len(display_score)):
        half = window_size // 2
        start_index = max(0, center - half)
        end_index = min(len(display_score) - 1, center + half)
        score = float(np.mean(display_score[start_index : end_index + 1]))
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
                "center_index": center,
                "center_ratio": center / max(len(display_score) - 1, 1),
                "start_seconds": round(float(timestamps[start_index]), 2),
                "end_seconds": round(float(timestamps[end_index]), 2),
                "start_ts": _format_ts(timestamps[start_index]),
                "end_ts": _format_ts(timestamps[end_index]),
            }
        )
        if len(selected) >= count:
            break
    return selected


def _window_label(window: dict[str, Any] | None) -> str:
    if not window:
        return ""
    start = str(window["start_ts"])
    end = str(window["end_ts"])
    return start if start == end else f"{start}-{end}"


def _window_phase(window: dict[str, Any] | None) -> str:
    if not window:
        return "middle"
    relative = float(window.get("center_ratio") or 0.0)
    if relative < 0.33:
        return "opening"
    if relative > 0.66:
        return "ending"
    return "middle"


def _summary_text_es(phase_states: dict[str, str]) -> str:
    opening = {
        "stronger": "El arranque está arriba del promedio del mismo cut.",
        "steady": "El arranque se mantiene cerca del resto del cut.",
        "weaker": "El arranque está abajo del resto del cut.",
    }[phase_states.get("opening", "steady")]
    middle = {
        "stronger": "La mitad aguanta arriba del promedio del cut.",
        "steady": "La mitad se mantiene pareja, sin caída clara.",
        "weaker": "La mitad es donde la curva cae respecto al resto del cut.",
    }[phase_states.get("middle", "steady")]
    ending = {
        "stronger": "El cierre vuelve a subir.",
        "steady": "El cierre se mantiene cerca del promedio del cut.",
        "weaker": "El cierre se ve más flojo que el resto del cut.",
    }[phase_states.get("ending", "steady")]
    return f"{opening} {middle} {ending}"


def _summary_text_en(phase_states: dict[str, str]) -> str:
    opening = {
        "stronger": "The opening sits above this cut's average.",
        "steady": "The opening stays close to the rest of the cut.",
        "weaker": "The opening sits below the rest of the cut.",
    }[phase_states.get("opening", "steady")]
    middle = {
        "stronger": "The middle holds above the cut average.",
        "steady": "The middle stays fairly even.",
        "weaker": "The middle is where the curve dips below the rest of the cut.",
    }[phase_states.get("middle", "steady")]
    ending = {
        "stronger": "The ending picks back up.",
        "steady": "The ending stays close to the cut average.",
        "weaker": "The ending looks weaker than the rest of the cut.",
    }[phase_states.get("ending", "steady")]
    return f"{opening} {middle} {ending}"


def _keep_text_es(strong_reference: dict[str, Any] | None) -> str:
    if not strong_reference:
        return "Toma los tramos más fuertes como referencia y no los muevas primero."
    label = _window_label(strong_reference)
    return (
        f"El tramo en {label} se ve más fuerte que el resto del cut. "
        "Tómalo de referencia y no le muevas primero."
    )


def _keep_text_en(strong_reference: dict[str, Any] | None) -> str:
    if not strong_reference:
        return "Use the strongest sections as the reference and do not change them first."
    label = _window_label(strong_reference)
    return (
        f"The section around {label} looks stronger than the rest of the cut. "
        "Use it as the reference and do not change it first."
    )


def _check_text_es(
    weak_reference: dict[str, Any] | None,
    strong_reference: dict[str, Any] | None,
) -> str:
    if not weak_reference:
        return "Revisa primero el tramo donde la curva cae abajo del promedio y compáralo con un tramo más fuerte."
    weak_label = _window_label(weak_reference)
    if strong_reference:
        strong_label = _window_label(strong_reference)
        return (
            f"Revisa primero el tramo en {weak_label}. Aquí la curva cae respecto al mismo cut. "
            f"Compáralo con el tramo más fuerte en {strong_label}: qué cambia en encuadre, movimiento, audio o voz."
        )
    return (
        f"Revisa primero el tramo en {weak_label}. Aquí la curva cae respecto al mismo cut. "
        "Mira qué cambia en encuadre, movimiento, audio o voz."
    )


def _check_text_en(
    weak_reference: dict[str, Any] | None,
    strong_reference: dict[str, Any] | None,
) -> str:
    if not weak_reference:
        return "Check the part where the curve falls below average first, then compare it with a stronger section."
    weak_label = _window_label(weak_reference)
    if strong_reference:
        strong_label = _window_label(strong_reference)
        return (
            f"Check the section around {weak_label} first. The curve drops there relative to this same cut. "
            f"Compare it with the stronger section around {strong_label}: what changes in framing, motion, sound, or speech."
        )
    return (
        f"Check the section around {weak_label} first. The curve drops there relative to this same cut. "
        "Look at what changes in framing, motion, sound, or speech."
    )


def _steps_text_es(
    weak_reference: dict[str, Any] | None,
    strong_reference: dict[str, Any] | None,
) -> list[str]:
    weak_label = _window_label(weak_reference)
    strong_label = _window_label(strong_reference)
    steps = []
    if weak_label and strong_label:
        steps.append(f"Compara el tramo flojo en {weak_label} con el tramo fuerte en {strong_label}.")
    elif weak_label:
        steps.append(f"Arranca por el tramo en {weak_label}: se ve más flojo que el resto del cut.")
    steps.append("Si vas a editar, arranca por los tramos flojos, no por los más fuertes.")
    steps.append("No leas esta pantalla como veredicto final de virality o retention de YouTube.")
    return steps


def _steps_text_en(
    weak_reference: dict[str, Any] | None,
    strong_reference: dict[str, Any] | None,
) -> list[str]:
    weak_label = _window_label(weak_reference)
    strong_label = _window_label(strong_reference)
    steps = []
    if weak_label and strong_label:
        steps.append(f"Compare the weaker section {weak_label} with the stronger section {strong_label}.")
    elif weak_label:
        steps.append(f"Start with the section around {weak_label}: it looks weaker than the rest of the cut.")
    steps.append("If you edit, start with the weaker sections, not the strongest ones.")
    steps.append("Do not read this screen as a final virality or YouTube retention verdict.")
    return steps


def _practical_summary_es(phase_states: dict[str, str], weak_reference: dict[str, Any] | None) -> str:
    weak_label = _window_label(weak_reference)
    if phase_states.get("opening") == "weaker":
        return "El problema central está en el arranque. Arranca por los primeros segundos: muestra lo principal antes y tumba el setup extra."
    if phase_states.get("ending") == "weaker":
        return f"El cut se cae cerca del cierre. Arranca por el tramo en {weak_label or 'el bache'}: conviene apurarlo o cerrar antes."
    if phase_states.get("middle") == "weaker":
        return f"El bache central está en la mitad. Arranca por el tramo en {weak_label or 'la mitad'}: conviene acortarlo o brincar antes al siguiente beat."
    return f"Arranca por el tramo en {weak_label or 'el bache'}: se ve más flojo que el resto del cut."


def _practical_summary_en(phase_states: dict[str, str], weak_reference: dict[str, Any] | None) -> str:
    weak_label = _window_label(weak_reference)
    if phase_states.get("opening") == "weaker":
        return "The main problem is the opening. Start with the first seconds: show the main thing earlier and cut extra setup."
    if phase_states.get("ending") == "weaker":
        return f"The cut weakens near the end. Start with {weak_label or 'the weak section'}: it likely needs a faster finish or an earlier end."
    if phase_states.get("middle") == "weaker":
        return f"The main dip is in the middle. Start with {weak_label or 'the middle section'}: it likely needs to be shorter or move to the next moment earlier."
    return f"Start with {weak_label or 'the weak section'} first: it looks weaker than the rest of the cut."


def _practical_cards_es(
    strong_reference: dict[str, Any] | None,
    weak_reference: dict[str, Any] | None,
    secondary_weak: dict[str, Any] | None,
    modalities: list[str],
) -> list[dict[str, str]]:
    cards = [
        {
            "title": "Deja como referencia",
            "detail": _keep_text_es(strong_reference),
        },
        _primary_fix_card_es(weak_reference),
        _next_test_card_es(weak_reference, secondary_weak, strong_reference, modalities),
    ]
    return cards


def _practical_cards_en(
    strong_reference: dict[str, Any] | None,
    weak_reference: dict[str, Any] | None,
    secondary_weak: dict[str, Any] | None,
    modalities: list[str],
) -> list[dict[str, str]]:
    cards = [
        {
            "title": "Keep as reference",
            "detail": _keep_text_en(strong_reference),
        },
        _primary_fix_card_en(weak_reference),
        _next_test_card_en(weak_reference, secondary_weak, strong_reference, modalities),
    ]
    return cards


def _primary_fix_card_es(weak_reference: dict[str, Any] | None) -> dict[str, str]:
    weak_label = _window_label(weak_reference)
    phase = _window_phase(weak_reference)
    if phase == "opening":
        return {
            "title": "Refuerza el arranque",
            "detail": f"En el tramo en {weak_label or 'el arranque'}, muestra lo principal más rápido: tumba el setup, empieza con un shot más claro o jala el mensaje hacia el inicio.",
        }
    if phase == "ending":
        return {
            "title": "Apura el cierre",
            "detail": f"En el tramo en {weak_label or 'el cierre'}, el cut se cae. Prueba un cierre más temprano o brinca más rápido al beat final.",
        }
    return {
        "title": "Acorta el tramo arrastrado",
        "detail": f"En el tramo en {weak_label or 'la mitad'}, la curva cae. Tumba segundos antes de este punto o brinca más temprano a la acción nueva.",
    }


def _primary_fix_card_en(weak_reference: dict[str, Any] | None) -> dict[str, str]:
    weak_label = _window_label(weak_reference)
    phase = _window_phase(weak_reference)
    if phase == "opening":
        return {
            "title": "Strengthen the opening",
            "detail": f"In {weak_label or 'the opening'}, show the main thing earlier: cut setup, start with a clearer shot, or bring the message closer to the start.",
        }
    if phase == "ending":
        return {
            "title": "Speed up the ending",
            "detail": f"In {weak_label or 'the ending'}, the cut weakens. Test an earlier finish or a faster move to the final beat.",
        }
    return {
        "title": "Shorten this section",
        "detail": f"In {weak_label or 'the middle section'}, the curve dips. Try a shorter version or move to the next moment earlier.",
    }


def _next_test_card_es(
    weak_reference: dict[str, Any] | None,
    secondary_weak: dict[str, Any] | None,
    strong_reference: dict[str, Any] | None,
    modalities: list[str],
) -> dict[str, str]:
    weak_label = _window_label(weak_reference)
    strong_label = _window_label(strong_reference)
    text_modalities = {"word", "sentence", "text"}
    if text_modalities.intersection({item.lower() for item in modalities}):
        return {
            "title": "Siguiente test",
            "detail": f"Si el mensaje vive en las palabras, prueba una versión donde la frase clave aterrice antes o justo al inicio del tramo en {weak_label or 'el bache'}. Compara con el tramo más fuerte en {strong_label or 'la curva'}.",
        }
    target = _window_label(secondary_weak) or weak_label or "el bache"
    return {
        "title": "Siguiente test",
        "detail": f"Después del primer ajuste, revisa el tramo en {target}. Compáralo con el tramo más fuerte en {strong_label or 'la curva'} y mira si un cambio de shot, ángulo o acción más temprano ayuda.",
    }


def _next_test_card_en(
    weak_reference: dict[str, Any] | None,
    secondary_weak: dict[str, Any] | None,
    strong_reference: dict[str, Any] | None,
    modalities: list[str],
) -> dict[str, str]:
    weak_label = _window_label(weak_reference)
    strong_label = _window_label(strong_reference)
    text_modalities = {"word", "sentence", "text"}
    if text_modalities.intersection({item.lower() for item in modalities}):
        return {
            "title": "Next test",
            "detail": f"If the message lives in the spoken line, test a version where the key phrase lands before or right at the start of {weak_label or 'the weak section'}. Compare it with the stronger section {strong_label or 'on the curve'}.",
        }
    target = _window_label(secondary_weak) or weak_label or "the weak section"
    return {
        "title": "Next test",
        "detail": f"After the first edit, check {target}. Compare it with the stronger section {strong_label or 'on the curve'} and see whether an earlier shot, angle, or action helps.",
    }


def _build_svg_points(values: np.ndarray, width: int = 860, height: int = 210, padding: int = 18) -> str:
    if not len(values):
        return ""
    return " ".join(
        f"{_svg_xy(index, values, width, height, padding)[0]:.2f},{_svg_xy(index, values, width, height, padding)[1]:.2f}"
        for index in range(len(values))
    )


def _svg_xy(index: int, values: np.ndarray, width: int, height: int, padding: int) -> tuple[float, float]:
    x = width / 2.0 if len(values) == 1 else padding + (width - 2 * padding) * (index / (len(values) - 1))
    y = height - padding - (height - 2 * padding) * (float(values[index]) / 100.0)
    return x, y
