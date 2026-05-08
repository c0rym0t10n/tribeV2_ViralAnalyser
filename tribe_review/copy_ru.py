"""Russian copy strings and copy-related helpers.

Currently re-exports from :mod:`tribe_review._engine` so callers can import
from a stable, topic-shaped namespace::

    from tribe_review.copy_ru import ACTION_VARIANTS, _signal_note

The actual function bodies will migrate into this module in a follow-up PR
(see TODO at the top of ``_engine.py``).
"""

from __future__ import annotations

from tribe_review._engine import (
    ACTION_VARIANTS,
    USER_METRIC_LABELS,
    _articulation_summary,
    _confidence_summary,
    _density_summary,
    _early_response_summary,
    _friendly_metric_label,
    _metric_label,
    _metric_summary,
    _pause_summary,
    _score_bucket,
    _signal_note,
    _simple_metric_action,
    _speech_pace_summary,
    _speech_start_summary,
    _stability_summary,
    _sustain_summary,
    _transition_summary,
)

__all__ = [
    "ACTION_VARIANTS",
    "USER_METRIC_LABELS",
    "_articulation_summary",
    "_confidence_summary",
    "_density_summary",
    "_early_response_summary",
    "_friendly_metric_label",
    "_metric_label",
    "_metric_summary",
    "_pause_summary",
    "_score_bucket",
    "_signal_note",
    "_simple_metric_action",
    "_speech_pace_summary",
    "_speech_start_summary",
    "_stability_summary",
    "_sustain_summary",
    "_transition_summary",
]
