from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisModeProfile:
    key: str
    label: str
    short_label: str
    description: str
    ui_note: str
    min_segment_word_probability: float
    max_segment_no_speech_probability: float
    min_total_words: int
    min_total_speech_seconds: float
    min_average_word_probability: float
    drop_activation_z_threshold: float
    drop_novelty_z_threshold: float
    max_drop_markers: int
    recommendation_cutoff: int
    comparison_spread_note: str
    max_action_items: int


ANALYSIS_MODE_PROFILES: dict[str, AnalysisModeProfile] = {
    "deep": AnalysisModeProfile(
        key="deep",
        label="Análisis a profundidad",
        short_label="Deep",
        description="Explica todo a detalle: la curva, los baches y la diferencia entre versiones.",
        ui_note="Útil cuando quieres entender por qué el video aguanta o se cae, no solo una lista corta de ajustes.",
        min_segment_word_probability=0.28,
        max_segment_no_speech_probability=0.58,
        min_total_words=2,
        min_total_speech_seconds=0.4,
        min_average_word_probability=0.62,
        drop_activation_z_threshold=-0.65,
        drop_novelty_z_threshold=-0.2,
        max_drop_markers=6,
        recommendation_cutoff=66,
        comparison_spread_note="Modo más sensible: muestra no solo al ganador, sino por qué métricas una versión le gana a la otra.",
        max_action_items=6,
    ),
    "simplified": AnalysisModeProfile(
        key="simplified",
        label="Simplificado",
        short_label="Simple",
        description="Habla directo: qué dejar, qué arreglar y en qué segundo hacerlo.",
        ui_note="Útil cuando quieres una conclusión corta sin análisis extra: abrir el reporte, entender qué cambiar, ir a editar.",
        min_segment_word_probability=0.36,
        max_segment_no_speech_probability=0.42,
        min_total_words=3,
        min_total_speech_seconds=0.6,
        min_average_word_probability=0.72,
        drop_activation_z_threshold=-0.85,
        drop_novelty_z_threshold=-0.42,
        max_drop_markers=4,
        recommendation_cutoff=60,
        comparison_spread_note="Modo más práctico: solo saca las diferencias que se traducen fácil en el siguiente cambio.",
        max_action_items=4,
    ),
}

DEFAULT_ANALYSIS_MODE = "deep"


def get_analysis_mode_profile(key: str | None) -> AnalysisModeProfile:
    if not key:
        return ANALYSIS_MODE_PROFILES[DEFAULT_ANALYSIS_MODE]
    return ANALYSIS_MODE_PROFILES.get(key, ANALYSIS_MODE_PROFILES[DEFAULT_ANALYSIS_MODE])
