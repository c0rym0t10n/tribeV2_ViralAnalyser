"""Russian copy strings and copy-related helpers.

Owns the per-metric labels, the small ``_simple_metric_action`` mapping, and
thin delegators for the conditional-copy summaries (the actual band tables
moved to :mod:`report_localization` in Stage-2 / G3).

Pure data + tiny string helpers — no numpy, no engine state. Importable on
its own.

The ``ACTION_VARIANTS`` constant is sourced from :mod:`report_localization`
(F3); this module re-exports it under the historical name so existing
callers keep one stable import path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from analysis_settings import AnalysisModeProfile

# Re-export ACTION_VARIANTS from report_localization (the F3 follow-up moved
# the table there). ``noqa: F401`` because the alias name differs from the
# imported symbol — ruff doesn't auto-classify that as a re-export.
from report_localization import ACTION_VARIANTS_RU as ACTION_VARIANTS  # noqa: F401
if TYPE_CHECKING:
    # ``_simple_metric_action`` only reads ``metric.key``; we don't need the
    # ``ReviewMetric`` class at runtime, but keeping the type hint explicit
    # helps editors / mypy.
    from tribe_review.metrics import ReviewMetric  # noqa: F401


USER_METRIC_LABELS: dict[str, str] = {
    "early_response": "Старт графика",
    "sustain": "Как держится график",
    "transition": "Темп событий",
    "stability": "Резкие просадки",
    "density": "Средний уровень",
}


def _friendly_metric_label(key: str, fallback: str | None = None) -> str:
    return USER_METRIC_LABELS.get(str(key), fallback or str(key))


def _metric_label(key: str, profile: AnalysisModeProfile) -> str:
    del profile
    return _friendly_metric_label(key)


def _signal_note(profile: AnalysisModeProfile) -> str:
    del profile
    return "Ниже показан расчетный график ролика: где уровень выше, где есть просадки и какие места стоит проверить в монтаже. Это подсказка для сравнительных тестов, а не обещание результата."


def _simple_metric_action(metric: ReviewMetric) -> str:
    actions = {
        "early_response": "Усиль старт: покажи главное раньше, убери длинный подвод и сделай первый кадр понятнее.",
        "sustain": "Подрежь участок перед просадкой или добавь там новый поворот, чтобы линия не падала после сильного момента.",
        "transition": "Добавь новое событие раньше: другой план, ракурс, действие, жест или короткую текстовую опору.",
        "stability": "Сглади резкую просадку: оставь один главный объект и убери детали, которые спорят за внимание.",
        "density": "Подними средний уровень: крупнее главный объект, чище фон, заметнее действие или сильнее контраст.",
    }
    return actions.get(metric.key, "Упрости этот участок и сделай главный объект заметнее.")
