"""Regression tests for Follow-up F3 (i18n consolidation)."""

from __future__ import annotations

import pytest

from report_localization import (
    ACTION_VARIANTS_EN,
    ACTION_VARIANTS_RU,
    CURVE_FOCUS_WINDOW_LABELS_EN,
    CURVE_FOCUS_WINDOW_LABELS_RU,
    CURVE_FOCUS_WINDOW_SUMMARIES_EN,
    CURVE_FOCUS_WINDOW_SUMMARIES_RU,
    LABEL_MAP_EN,
    get_action_variants,
)


@pytest.mark.parametrize("metric_key", list(ACTION_VARIANTS_RU))
def test_action_variants_ru_en_have_same_shape(metric_key: str) -> None:
    """Each metric category must have the same number of (title, instruction)
    pairs in RU and EN so an EN consumer can index by variant_index without
    falling off the end."""

    ru = ACTION_VARIANTS_RU[metric_key]
    en = ACTION_VARIANTS_EN.get(metric_key, [])
    assert len(ru) == len(en), (
        f"ACTION_VARIANTS_{{RU,EN}} for `{metric_key}` mismatched: "
        f"RU={len(ru)} EN={len(en)}"
    )
    for ru_pair, en_pair in zip(ru, en):
        assert isinstance(ru_pair, tuple) and len(ru_pair) == 2
        assert isinstance(en_pair, tuple) and len(en_pair) == 2
        assert all(isinstance(s, str) and s.strip() for s in ru_pair)
        assert all(isinstance(s, str) and s.strip() for s in en_pair)


def test_get_action_variants_defaults_to_russian() -> None:
    assert get_action_variants() is ACTION_VARIANTS_RU
    assert get_action_variants(None) is ACTION_VARIANTS_RU
    assert get_action_variants("ru") is ACTION_VARIANTS_RU
    assert get_action_variants("EN") is ACTION_VARIANTS_EN
    assert get_action_variants("en") is ACTION_VARIANTS_EN


def test_curve_alignment_default_tuples_match_length() -> None:
    """The RU/EN tuples for focus-window labels and summaries must align so
    `_build_curve_focus_windows` can index either side by the same position."""

    assert len(CURVE_FOCUS_WINDOW_LABELS_RU) == len(CURVE_FOCUS_WINDOW_LABELS_EN)
    assert len(CURVE_FOCUS_WINDOW_SUMMARIES_RU) == len(CURVE_FOCUS_WINDOW_SUMMARIES_EN)
    assert len(CURVE_FOCUS_WINDOW_LABELS_RU) >= 3
    assert len(CURVE_FOCUS_WINDOW_SUMMARIES_RU) >= 3


def test_label_map_en_covers_all_action_variant_titles() -> None:
    """Side-effect of the population block at the end of report_localization.py:
    every Russian title and instruction must be reachable as a key in
    LABEL_MAP_EN, otherwise ``_apply_known_labels`` won't translate them."""

    missing: list[str] = []
    for ru_pairs in ACTION_VARIANTS_RU.values():
        for ru_title, ru_instruction in ru_pairs:
            if ru_title not in LABEL_MAP_EN:
                missing.append(ru_title)
            if ru_instruction not in LABEL_MAP_EN:
                missing.append(ru_instruction)
    assert not missing, f"missing EN translations for: {missing[:5]}"


def test_copy_ru_reexports_action_variants_from_localization() -> None:
    """``tribe_review.copy_ru.ACTION_VARIANTS`` must be the same object as
    ``report_localization.ACTION_VARIANTS_RU`` (no separate copy living in
    the package). After G2, ``copy_ru`` is the canonical home for this
    re-export — the legacy ``tribe_review._engine.ACTION_VARIANTS`` path
    still resolves via re-export but copy_ru is the source of truth.

    Skips when the package can't be imported (e.g. heavy deps absent in a
    minimal sandbox).
    """

    try:
        from tribe_review.copy_ru import ACTION_VARIANTS as copy_ru_variants
    except ModuleNotFoundError as exc:
        pytest.skip(f"tribe_review.copy_ru cannot be imported: {exc!r}")

    assert copy_ru_variants is ACTION_VARIANTS_RU


def test_package_root_reexports_action_variants() -> None:
    """``from tribe_review import ACTION_VARIANTS`` must keep working — that's
    the public-surface path used by ``app.py`` and external callers."""

    try:
        from tribe_review import ACTION_VARIANTS as package_variants
    except ModuleNotFoundError as exc:
        pytest.skip(f"tribe_review cannot be imported: {exc!r}")

    assert package_variants is ACTION_VARIANTS_RU


def test_action_variants_dict_literal_not_reintroduced() -> None:
    """Static check: the ``ACTION_VARIANTS`` dict literal should NOT live in
    any ``tribe_review`` module — it must always be imported from
    ``report_localization``. Guards against regressions where someone
    re-inlines the table.

    Post-G2 the canonical import lives in ``copy_ru.py`` rather than
    ``_engine.py``; we still want the assertion that the literal isn't
    sitting in source anywhere.
    """

    from pathlib import Path

    pkg_dir = Path(__file__).resolve().parent.parent / "tribe_review"
    copy_ru_text = (pkg_dir / "copy_ru.py").read_text(encoding="utf-8")

    assert "ACTION_VARIANTS_RU as ACTION_VARIANTS" in copy_ru_text, (
        "F3 regression: tribe_review/copy_ru.py is no longer importing "
        "ACTION_VARIANTS from report_localization."
    )

    sentinel = '"early_response": [\n        ("Усиль первый кадр"'
    for module in pkg_dir.glob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert sentinel not in text, (
            f"F3 regression: ACTION_VARIANTS dict literal returned to {module.name}"
        )
