"""Public surface for the TRIBE review engine.

Phase-2 of the refactor scaffolded this package as a stable import target.
Follow-up F1 dropped the legacy top-level ``review_engine.py`` (which was
2437 LOC with 45 dead duplicate function definitions) and consolidated the
canonical engine into :mod:`tribe_review._engine`. Topic-shaped sibling
modules (``copy_ru``, ``metrics``, ``timeline``, ``recommendations``,
``comparison``) re-export from ``_engine`` so callers can already migrate to
``from tribe_review.metrics import ReviewMetric`` etc. The actual function
bodies will move into those modules once snapshot-test fixtures exist to
verify behaviour parity.

Public API::

    from tribe_review import generate_review, generate_comparison_report
    from tribe_review import ReviewMetric, SpeechMetric, FocusWindow, ACTION_VARIANTS
"""

from __future__ import annotations

from tribe_review._engine import (
    ACTION_VARIANTS,
    FocusWindow,
    ReviewMetric,
    SpeechMetric,
    generate_comparison_report,
    generate_review,
)

__all__ = [
    "ACTION_VARIANTS",
    "FocusWindow",
    "ReviewMetric",
    "SpeechMetric",
    "generate_comparison_report",
    "generate_review",
]
