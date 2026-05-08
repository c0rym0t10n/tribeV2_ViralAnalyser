"""Unit tests for ``report_localization``."""

from __future__ import annotations

import pytest

from report_localization import (
    DEFAULT_REPORT_LANGUAGE,
    SUPPORTED_REPORT_LANGUAGES,
    get_ui_texts,
    localize_analysis_mode_options,
    normalize_report_language,
)


@pytest.mark.parametrize(
    "value",
    [None, "", "  ", "fr", "EN-US", "INVALID", "klingon"],
)
def test_normalize_report_language_falls_back_to_default(value: str | None) -> None:
    assert normalize_report_language(value) == DEFAULT_REPORT_LANGUAGE


def test_normalize_report_language_keeps_supported_lowercase() -> None:
    for lang in SUPPORTED_REPORT_LANGUAGES:
        assert normalize_report_language(lang) == lang
        assert normalize_report_language(lang.upper()) == lang


def test_get_ui_texts_returns_dict_for_supported_languages() -> None:
    for lang in SUPPORTED_REPORT_LANGUAGES:
        ui = get_ui_texts(lang)
        assert isinstance(ui, dict)
        assert ui  # not empty


def test_get_ui_texts_falls_back_for_unknown_language() -> None:
    ui = get_ui_texts("nonexistent")
    assert isinstance(ui, dict)
    assert ui


def test_localize_analysis_mode_options_for_default_language() -> None:
    options = localize_analysis_mode_options(DEFAULT_REPORT_LANGUAGE)
    assert isinstance(options, list)
    assert options, "expected at least one analysis-mode option"
    keys = {item["key"] for item in options}
    assert {"deep", "simplified"} <= keys
    for item in options:
        assert {"key", "label", "short_label", "description"} <= set(item)
