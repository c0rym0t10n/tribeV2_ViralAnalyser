"""Multi-variant comparison logic.

Currently re-exports from :mod:`tribe_review._engine`. Function bodies will
migrate here in a follow-up PR.
"""

from __future__ import annotations

from tribe_review._engine import (
    _build_axis_winners,
    _build_compare_executive_summary,
    _build_compare_product_summary,
    _build_compare_verdict,
    _build_common_gaps,
    _build_comparison_recommendations,
    _build_comparison_rows,
    _build_ranking,
    _comparison_score_value,
    _comparison_signal_score,
    _comparison_usable_end,
    _comparison_value,
    _prepare_comparison_variants,
    _variant_compare_summary,
    _variant_metric,
    generate_comparison_report,
)

__all__ = [
    "_build_axis_winners",
    "_build_compare_executive_summary",
    "_build_compare_product_summary",
    "_build_compare_verdict",
    "_build_common_gaps",
    "_build_comparison_recommendations",
    "_build_comparison_rows",
    "_build_ranking",
    "_comparison_score_value",
    "_comparison_signal_score",
    "_comparison_usable_end",
    "_comparison_value",
    "_prepare_comparison_variants",
    "_variant_compare_summary",
    "_variant_metric",
    "generate_comparison_report",
]
