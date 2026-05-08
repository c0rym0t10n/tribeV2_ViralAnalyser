"""Public surface for the TRIBE review engine.

This package is the long-term home for what currently lives in
``review_engine.py`` (and parts of ``app.py``). Phase 2 of the refactor plan
established the package as a stable import target so that downstream modules
can start importing from ``tribe_review`` instead of ``review_engine``. The
internal split into ``metrics``, ``recommendations``, ``comparison``,
``timeline``, and ``copy_ru`` will land in a follow-up PR once test coverage
exists to verify behaviour parity.

For now we re-export the canonical entry points from the legacy module so
callers can migrate at their own pace::

    from tribe_review import generate_review, generate_comparison_report
"""

from __future__ import annotations

from review_engine import (
    ACTION_VARIANTS,
    ReviewMetric,
    FocusWindow,
    generate_comparison_report,
    generate_review,
)

__all__ = [
    "ACTION_VARIANTS",
    "ReviewMetric",
    "FocusWindow",
    "generate_comparison_report",
    "generate_review",
]
