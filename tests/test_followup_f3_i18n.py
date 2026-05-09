"""Regression tests for Follow-up F3 (i18n consolidation), updated for
Stage 3 / S1 which dropped RU and made ES the source-of-truth language."""

from __future__ import annotations

import pytest

from report_localization import (
    ACTION_VARIANTS_EN,
    ACTION_VARIANTS_ES,
    CURVE_FOCUS_WINDOW_LABELS_EN,
    CURVE_FOCUS_WINDOW_LABELS_ES,
    CURVE_FOCUS_WINDOW_SUMMARIES_EN,
    CURVE_FOCUS_WINDOW_SUMMARIES_ES,
    LABEL_MAP_EN,
    get_action_variants,
)


@pytest.mark.parametrize("metric_key", list(ACTION_VARIANTS_ES))
def test_action_variants_es_en_have_same_shape(metric_key: str) -> None:
    """Each metric category must have the same number of (title, instruction)
    pairs in ES and EN so an EN consumer can index by variant_index without
    falling off the end."""

    es = ACTION_VARIANTS_ES[metric_key]
    en = ACTION_VARIANTS_EN.get(metric_key, [])
    assert len(es) == len(en), (
        f"ACTION_VARIANTS_{{ES,EN}} for `{metric_key}` mismatched: "
        f"ES={len(es)} EN={len(en)}"
    )
    for es_pair, en_pair in zip(es, en):
        assert isinstance(es_pair, tuple) and len(es_pair) == 2
        assert isinstance(en_pair, tuple) and len(en_pair) == 2
        assert all(isinstance(s, str) and s.strip() for s in es_pair)
        assert all(isinstance(s, str) and s.strip() for s in en_pair)


def test_get_action_variants_defaults_to_spanish() -> None:
    assert get_action_variants() is ACTION_VARIANTS_ES
    assert get_action_variants(None) is ACTION_VARIANTS_ES
    assert get_action_variants("es") is ACTION_VARIANTS_ES
    assert get_action_variants("EN") is ACTION_VARIANTS_EN
    assert get_action_variants("en") is ACTION_VARIANTS_EN


def test_curve_alignment_default_tuples_match_length() -> None:
    """The ES/EN tuples for focus-window labels and summaries must align so
    `_build_curve_focus_windows` can index either side by the same position."""

    assert len(CURVE_FOCUS_WINDOW_LABELS_ES) == len(CURVE_FOCUS_WINDOW_LABELS_EN)
    assert len(CURVE_FOCUS_WINDOW_SUMMARIES_ES) == len(CURVE_FOCUS_WINDOW_SUMMARIES_EN)
    assert len(CURVE_FOCUS_WINDOW_LABELS_ES) >= 3
    assert len(CURVE_FOCUS_WINDOW_SUMMARIES_ES) >= 3


def test_label_map_en_covers_all_action_variant_titles() -> None:
    """Side-effect of the population block at the end of report_localization.py:
    every Spanish title and instruction must be reachable as a key in
    LABEL_MAP_EN, otherwise ``_apply_known_labels`` won't translate them.

    Stage 3 / S1 retrained the population block from RU-keyed to ES-keyed.
    """

    missing: list[str] = []
    for es_pairs in ACTION_VARIANTS_ES.values():
        for es_title, es_instruction in es_pairs:
            if es_title not in LABEL_MAP_EN:
                missing.append(es_title)
            if es_instruction not in LABEL_MAP_EN:
                missing.append(es_instruction)
    assert not missing, f"missing EN translations for: {missing[:5]}"


def test_copy_es_reexports_action_variants_from_localization() -> None:
    """``tribe_review.copy_es.ACTION_VARIANTS`` must be the same object as
    ``report_localization.ACTION_VARIANTS_ES``.

    Skips when the package can't be imported (e.g. heavy deps absent in a
    minimal sandbox).
    """

    try:
        from tribe_review.copy_es import ACTION_VARIANTS as copy_es_variants
    except ModuleNotFoundError as exc:
        pytest.skip(f"tribe_review.copy_es cannot be imported: {exc!r}")

    assert copy_es_variants is ACTION_VARIANTS_ES


def test_package_root_reexports_action_variants() -> None:
    """``from tribe_review import ACTION_VARIANTS`` must keep working — that's
    the public-surface path used by ``app.py`` and external callers."""

    try:
        from tribe_review import ACTION_VARIANTS as package_variants
    except ModuleNotFoundError as exc:
        pytest.skip(f"tribe_review cannot be imported: {exc!r}")

    assert package_variants is ACTION_VARIANTS_ES


def test_action_variants_dict_literal_not_reintroduced() -> None:
    """Static check: the ``ACTION_VARIANTS`` dict literal should NOT live in
    any ``tribe_review`` module — it must always be imported from
    ``report_localization``. Guards against regressions where someone
    re-inlines the table.

    Stage 3 / S1 dropped the RU table; the canonical import line lives in
    ``copy_es.py``. The legacy RU sentinel is kept in this scan so a
    re-introduced RU block would also fail loudly.
    """

    from pathlib import Path

    pkg_dir = Path(__file__).resolve().parent.parent / "tribe_review"
    copy_es_text = (pkg_dir / "copy_es.py").read_text(encoding="utf-8")

    assert "ACTION_VARIANTS_ES as ACTION_VARIANTS" in copy_es_text, (
        "F3 regression: tribe_review/copy_es.py is no longer importing "
        "ACTION_VARIANTS_ES from report_localization."
    )

    ru_sentinel = '"early_response": [\n        ("Усиль первый кадр"'
    es_sentinel = '"early_response": [\n        ("Refuerza el primer frame"'
    for module in pkg_dir.glob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert ru_sentinel not in text, (
            f"F3 regression: RU ACTION_VARIANTS dict literal in {module.name}"
        )
        assert es_sentinel not in text, (
            f"F3 regression: ES ACTION_VARIANTS dict literal in {module.name}"
        )
