"""Spanish (México coloquial) copy strings and copy-related helpers.

Owns the per-metric labels (deep-mode descriptive ES), the small
``_simple_metric_action`` mapping, and the ``_signal_note`` short caption.
Banded summaries (metric + speech) live in :mod:`report_localization` —
this module only carries the labels and inline copy that the engine
emits regardless of band.

Pure data + tiny string helpers — no numpy, no engine state. Importable
on its own.

The ``ACTION_VARIANTS`` constant is sourced from :mod:`report_localization`;
this module re-exports it under the historical name so existing callers
keep one stable import path.

Stage 3 / S1 replaced the previous ``copy_ru`` module; the file rename also
flipped the imports across the engine modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from analysis_settings import AnalysisModeProfile

# Re-export ACTION_VARIANTS from report_localization (the F3 follow-up moved
# the table there). ``noqa: F401`` because the alias name differs from the
# imported symbol — ruff doesn't auto-classify that as a re-export.
from report_localization import ACTION_VARIANTS_ES as ACTION_VARIANTS  # noqa: F401

if TYPE_CHECKING:
    # ``_simple_metric_action`` only reads ``metric.key``; we don't need the
    # ``ReviewMetric`` class at runtime, but keeping the type hint explicit
    # helps editors / mypy.
    from tribe_review.metrics import ReviewMetric  # noqa: F401


# Deep-mode metric labels (descriptive ES). Simplified-mode flips these to
# TikTok jargon (Hook / Retention / Pacing / Visual clarity / Visual punch)
# in :mod:`ollama_sanitize._simplify_metrics`.
USER_METRIC_LABELS: dict[str, str] = {
    "early_response": "Arranque de la curva",
    "sustain": "Cómo aguanta la curva",
    "transition": "Ritmo del cambio",
    "stability": "Bajones bruscos",
    "density": "Fuerza visual",
}


def _friendly_metric_label(key: str, fallback: str | None = None) -> str:
    return USER_METRIC_LABELS.get(str(key), fallback or str(key))


def _metric_label(key: str, profile: AnalysisModeProfile) -> str:
    del profile
    return _friendly_metric_label(key)


def _signal_note(profile: AnalysisModeProfile) -> str:
    del profile
    return "Esta curva es una pista para tu A/B, no garantía."


def _simple_metric_action(metric: ReviewMetric) -> str:
    actions = {
        "early_response": "Mete el hook desde el primer shot, tumba el setup largo y entra al beat principal de volada.",
        "sustain": "Acorta el tramo antes del bache o métele un giro nuevo para que la curva no se caiga.",
        "transition": "Cambia el shot antes — otro plano, ángulo, acción, gesto o un caption corto.",
        "stability": "Limpia el frame: deja un objeto principal y tumba los detalles que pelean por la atención.",
        "density": "Sube la base visual: objeto más grande, fondo más limpio, acción más clara o más contraste.",
    }
    return actions.get(metric.key, "Simplifica este tramo y haz que el objeto principal esté más claro.")
