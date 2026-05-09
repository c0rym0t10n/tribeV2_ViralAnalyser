from __future__ import annotations

from functools import lru_cache
from math import ceil
from typing import Any

import numpy as np
from tribev2.plotting.cortical import PlotBrainNilearn


BRAIN_MESH_LEVEL = "fsaverage5"
MIN_BRAIN_FRAMES = 24
MAX_BRAIN_FRAMES = 40
TARGET_BRAIN_FPS = 1.45
SIGNAL_QUANTIZATION = 255

REGION_DEFINITIONS = (
    {
        "key": "frontal",
        "id": 1,
        "color": "#d6c46d",
        "label_es": "Zona frontal",
        "label_en": "Frontal zone",
        "description_es": "Ayuda a evaluar significado, intención y qué importa más en el frame.",
        "description_en": "Helps evaluate meaning, intent, and what matters most in the frame.",
    },
    {
        "key": "sensorimotor",
        "id": 2,
        "color": "#d4a97b",
        "label_es": "Zona de acción",
        "label_en": "Action zone",
        "description_es": "Reacciona más a movimiento, gestos, acción física y cambios de postura.",
        "description_en": "Tracks movement, gestures, physical action, and body dynamics.",
    },
    {
        "key": "parietal",
        "id": 3,
        "color": "#8fb38d",
        "label_es": "Zona de atención",
        "label_en": "Attention zone",
        "description_es": "Relacionada con cómo se reparte la atención por el frame y a dónde mira el espectador.",
        "description_en": "Relates to how attention spreads across the frame and where the viewer is likely to look.",
    },
    {
        "key": "temporal",
        "id": 4,
        "color": "#b6819b",
        "label_es": "Zona de voz y reconocimiento",
        "label_en": "Speech and recognition zone",
        "description_es": "Participa en el reconocimiento de voz, sonido, caras y objetos familiares.",
        "description_en": "Supports speech, sound, face, and familiar-object recognition.",
    },
    {
        "key": "occipital",
        "id": 5,
        "color": "#7d89b5",
        "label_es": "Zona visual",
        "label_en": "Visual zone",
        "description_es": "Procesa la imagen misma: forma, contraste, color, movimiento y detalle.",
        "description_en": "Processes the image itself: shape, contrast, color, motion, and detail.",
    },
)


def build_brain_simulation(
    preds: Any,
    timestamps: list[float],
) -> dict[str, Any]:
    preds_np = np.asarray(preds)
    if preds_np.ndim != 2 or preds_np.shape[0] == 0:
        return {
            "available": False,
            "message": "TRIBE did not return a usable cortical map for 3D visualization.",
            "frames": [],
        }

    timeline = _build_time_axis(preds_np.shape[0], timestamps)
    duration_seconds = float(timeline[-1]) if timeline.size else 0.0
    target_frames = int(
        max(
            MIN_BRAIN_FRAMES,
            min(MAX_BRAIN_FRAMES, ceil(max(duration_seconds, 1.0) * TARGET_BRAIN_FPS)),
        )
    )
    frame_times = np.linspace(0.0, max(duration_seconds, 1e-6), num=target_frames)

    mesh_bundle = _load_mesh_bundle(BRAIN_MESH_LEVEL)
    plotter = mesh_bundle["plotter"]
    region_masks = mesh_bundle["region_masks"]
    region_meta = mesh_bundle["region_meta"]

    activity_np = _smooth_temporal(np.abs(preds_np.astype(float)))
    stat_maps: list[np.ndarray] = []
    for frame_time in frame_times:
        signal = _interpolate_signal(activity_np, timeline, frame_time)
        stat_maps.append(np.clip(np.asarray(plotter.get_stat_map(signal)["both"], dtype=float), 0.0, None))

    stat_map_stack = np.asarray(stat_maps, dtype=float)
    vmax = float(np.percentile(stat_map_stack, 99.3)) if stat_map_stack.size else 1.0
    vmax = max(vmax, 1e-6)
    threshold = max(float(np.percentile(stat_map_stack, 97.4)), vmax * 0.74)

    frames: list[dict[str, Any]] = []
    for frame_no, (frame_time, stat_map) in enumerate(zip(frame_times, stat_maps, strict=False)):
        normalized_signal = _normalize_signal_map(stat_map, threshold=threshold, vmax=vmax)
        region_scores, region_peak_scores = _compute_region_scores(normalized_signal, region_masks)
        frames.append(
            {
                "index": frame_no,
                "seconds": round(float(frame_time), 2),
                "timestamp": _format_ts(frame_time),
                "signal": np.rint(normalized_signal * SIGNAL_QUANTIZATION).astype(np.uint8).tolist(),
                "region_scores": [round(float(item), 4) for item in region_scores],
                "region_peak_scores": [round(float(item), 4) for item in region_peak_scores],
            }
        )

    return {
        "available": True,
        "message": "Modelo gris que puedes girar con el mouse. Los puntos brillantes muestran dónde el cut se ve más fuerte ahorita.",
        "frame_count": len(frames),
        "mesh_level": f"{BRAIN_MESH_LEVEL} detailed surface",
        "fps_hint": round(len(frames) / max(duration_seconds + 1e-6, 1.0), 3),
        "mesh": {
            "faces": mesh_bundle["faces"].reshape(-1).astype(int).tolist(),
            "bg_map": np.rint(mesh_bundle["bg_map"] * SIGNAL_QUANTIZATION).astype(np.uint8).tolist(),
            "region_ids": mesh_bundle["region_ids"].astype(np.uint8).tolist(),
            "regions": region_meta,
            "surfaces": {
                key: np.round(value.astype(np.float32).reshape(-1), 4).tolist()
                for key, value in mesh_bundle["surfaces"].items()
            },
            "default_surface": "inflated",
        },
        "frames": frames,
        "region_panel": {
            "title_es": "Zonas del cerebro en el análisis del video",
            "title_en": "Brain zones used in the video analysis",
            "hint_es": "Aquí se muestran todas las zonas grandes de la corteza que el modelo usa mientras ve el cut. Las barras indican qué zona está más activa en este momento.",
            "hint_en": "All major brain zones used by the model during the video are shown. The bars indicate which zone is more active at the current moment.",
        },
    }


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


def _normalize_coords(coords: np.ndarray) -> np.ndarray:
    centered = coords - coords.mean(axis=0, keepdims=True)
    radius = np.max(np.linalg.norm(centered, axis=1))
    return centered / max(radius, 1e-6)


def _normalize_bg(bg_map: np.ndarray) -> np.ndarray:
    low = float(bg_map.min())
    high = float(bg_map.max())
    norm = (bg_map - low) / max(high - low, 1e-6)
    return 0.24 + norm * 0.14


def _smooth_temporal(values: np.ndarray) -> np.ndarray:
    if values.ndim != 2 or values.shape[0] < 3:
        return values
    kernel = np.asarray([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
    kernel /= kernel.sum()
    padded = np.pad(values, ((2, 2), (0, 0)), mode="edge")
    smoothed = values.copy()
    for index in range(values.shape[0]):
        window = padded[index : index + kernel.size]
        smoothed[index] = np.tensordot(kernel, window, axes=(0, 0))
    return smoothed


def _normalize_signal_map(signal: np.ndarray, threshold: float, vmax: float) -> np.ndarray:
    scaled = np.clip((signal - threshold) / max(vmax - threshold, 1e-6), 0.0, 1.0)
    return np.power(scaled, 0.76)


def _interpolate_signal(activity_np: np.ndarray, timeline: np.ndarray, frame_time: float) -> np.ndarray:
    if activity_np.shape[0] == 1 or timeline.size <= 1:
        return activity_np[0]
    right = int(np.searchsorted(timeline, frame_time, side="left"))
    right = min(max(right, 1), activity_np.shape[0] - 1)
    left = right - 1
    left_time = float(timeline[left])
    right_time = float(timeline[right])
    if right_time <= left_time:
        return activity_np[right]
    ratio = (frame_time - left_time) / (right_time - left_time)
    return activity_np[left] * (1.0 - ratio) + activity_np[right] * ratio


def _compute_region_scores(signal: np.ndarray, region_masks: list[np.ndarray]) -> tuple[list[float], list[float]]:
    scores: list[float] = []
    peak_scores: list[float] = []
    for mask in region_masks:
        if mask.size == 0 or not mask.any():
            scores.append(0.0)
            peak_scores.append(0.0)
            continue
        region_values = signal[mask]
        blended = 0.7 * float(np.mean(region_values)) + 0.3 * float(np.percentile(region_values, 90))
        scores.append(blended)
        peak_scores.append(float(np.percentile(region_values, 99.2)))
    return scores, peak_scores


def _format_ts(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


@lru_cache(maxsize=1)
def _load_mesh_bundle(mesh_level: str) -> dict[str, Any]:
    normal_plotter = PlotBrainNilearn(mesh=mesh_level, inflate=False, bg_map="sulcal")
    inflated_plotter = PlotBrainNilearn(mesh=mesh_level, inflate="half", bg_map="sulcal")

    normal_mesh = normal_plotter._mesh["both"]
    inflated_mesh = inflated_plotter._mesh["both"]
    normal_coords = np.asarray(normal_mesh["coords"], dtype=float)
    region_ids, region_masks = _build_region_partition(normal_coords)

    return {
        "plotter": normal_plotter,
        "faces": np.asarray(normal_mesh["faces"], dtype=int),
        "bg_map": _normalize_bg(np.asarray(normal_mesh["bg_map"], dtype=float)),
        "region_ids": region_ids,
        "region_masks": region_masks,
        "region_meta": [
            {
                "id": int(item["id"]),
                "key": item["key"],
                "color": item["color"],
                "label_ru": item["label_ru"],
                "label_en": item["label_en"],
                "description_ru": item["description_ru"],
                "description_en": item["description_en"],
            }
            for item in REGION_DEFINITIONS
        ],
        "surfaces": {
            "normal": _normalize_coords(normal_coords),
            "inflated": _normalize_coords(np.asarray(inflated_mesh["coords"], dtype=float)),
        },
    }


def _build_region_partition(coords: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    normalized = _normalize_coords(coords)
    y = normalized[:, 1]
    z = normalized[:, 2]

    region_ids = np.zeros(len(normalized), dtype=np.uint8)

    occipital_mask = y < -0.42
    temporal_mask = (z < -0.2) & (y < 0.12)
    sensorimotor_mask = (y >= -0.08) & (y <= 0.12) & (z > -0.08)
    frontal_mask = y > 0.12
    parietal_mask = ~(occipital_mask | temporal_mask | sensorimotor_mask | frontal_mask)

    masks = {
        "frontal": frontal_mask,
        "sensorimotor": sensorimotor_mask,
        "parietal": parietal_mask,
        "temporal": temporal_mask,
        "occipital": occipital_mask,
    }

    ordered_masks: list[np.ndarray] = []
    for item in REGION_DEFINITIONS:
        mask = masks[item["key"]]
        region_ids[mask] = int(item["id"])
        ordered_masks.append(mask)
    return region_ids, ordered_masks
