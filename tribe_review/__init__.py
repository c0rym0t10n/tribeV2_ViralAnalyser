"""Public surface for the TRIBE review engine.

Stage-2 / G2 split the post-F1 monolith ``tribe_review._engine`` into
thematic modules:

* :mod:`tribe_review.copy_ru` — Russian copy strings + small label helpers.
* :mod:`tribe_review.metrics` — score math, signal-shape helpers, dataclasses.
* :mod:`tribe_review.timeline` — timeline build, focus windows, drop moments.
* :mod:`tribe_review.recommendations` — verdicts, summaries, recs, action items.
* :mod:`tribe_review.comparison` — multi-variant comparison + ``generate_comparison_report``.
* :mod:`tribe_review._engine` — orchestrator, owns ``generate_review`` only.

Public API::

    from tribe_review import generate_review, generate_comparison_report
    from tribe_review import ReviewMetric, SpeechMetric, FocusWindow, ACTION_VARIANTS
"""

from __future__ import annotations

from tribe_review._engine import generate_review
from tribe_review.comparison import generate_comparison_report
from tribe_review.copy_ru import ACTION_VARIANTS
from tribe_review.metrics import ReviewMetric, SpeechMetric
from tribe_review.timeline import FocusWindow

__all__ = [
    "ACTION_VARIANTS",
    "FocusWindow",
    "ReviewMetric",
    "SpeechMetric",
    "generate_comparison_report",
    "generate_review",
]
