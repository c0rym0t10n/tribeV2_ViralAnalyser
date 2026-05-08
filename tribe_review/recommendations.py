"""Verdict, summaries, recommendations, and action items.

Currently re-exports from :mod:`tribe_review._engine`. Function bodies will
migrate here in a follow-up PR.
"""

from __future__ import annotations

from tribe_review._engine import (
    _action_copy_for_metric,
    _action_metric_candidates,
    _build_action_items,
    _build_executive_summary,
    _build_product_summary,
    _build_recommendation_plan,
    _build_recommendations,
    _build_simple_recommendations,
    _build_strengths,
    _build_verdict,
    _build_weaknesses,
)

__all__ = [
    "_action_copy_for_metric",
    "_action_metric_candidates",
    "_build_action_items",
    "_build_executive_summary",
    "_build_product_summary",
    "_build_recommendation_plan",
    "_build_recommendations",
    "_build_simple_recommendations",
    "_build_strengths",
    "_build_verdict",
    "_build_weaknesses",
]
