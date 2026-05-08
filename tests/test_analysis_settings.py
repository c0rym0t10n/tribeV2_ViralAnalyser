"""Unit tests for ``analysis_settings``."""

from __future__ import annotations

import pytest

from analysis_settings import (
    ANALYSIS_MODE_PROFILES,
    DEFAULT_ANALYSIS_MODE,
    AnalysisModeProfile,
    get_analysis_mode_profile,
)


def test_default_mode_exists_in_profiles() -> None:
    assert DEFAULT_ANALYSIS_MODE in ANALYSIS_MODE_PROFILES


def test_profiles_contains_deep_and_simplified() -> None:
    assert {"deep", "simplified"} <= set(ANALYSIS_MODE_PROFILES)


@pytest.mark.parametrize("key", list(ANALYSIS_MODE_PROFILES))
def test_profile_round_trip(key: str) -> None:
    profile = get_analysis_mode_profile(key)
    assert isinstance(profile, AnalysisModeProfile)
    assert profile.key == key


def test_get_profile_with_none_returns_default() -> None:
    profile = get_analysis_mode_profile(None)
    assert profile.key == DEFAULT_ANALYSIS_MODE


def test_get_profile_with_empty_string_returns_default() -> None:
    profile = get_analysis_mode_profile("")
    assert profile.key == DEFAULT_ANALYSIS_MODE


def test_get_profile_with_invalid_key_returns_default() -> None:
    profile = get_analysis_mode_profile("not-a-real-mode")
    assert profile.key == DEFAULT_ANALYSIS_MODE


def test_profile_threshold_invariants() -> None:
    """Sanity check that profile numeric fields stay in their expected ranges."""
    for profile in ANALYSIS_MODE_PROFILES.values():
        assert 0.0 <= profile.min_segment_word_probability <= 1.0
        assert 0.0 <= profile.max_segment_no_speech_probability <= 1.0
        assert profile.min_total_words >= 1
        assert profile.min_total_speech_seconds > 0
        assert 0.0 <= profile.min_average_word_probability <= 1.0
        assert profile.max_drop_markers >= 1
        assert 0 <= profile.recommendation_cutoff <= 100
        assert profile.max_action_items >= 1
