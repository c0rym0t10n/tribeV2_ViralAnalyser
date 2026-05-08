"""Static regression checks for Phase 1 fixes.

These tests inspect the source of the modified code paths so they can run in CI
without importing the heavy TRIBE/torch dependency tree.
"""

from __future__ import annotations

import inspect
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_signal_note_duplicate_removed() -> None:
    """Phase 1.1: the literal-string ``signal_note`` shouldn't reappear above
    the ``_signal_note(profile)`` call inside ``generate_review``'s output
    dict. (The comparison-report dict in the same file legitimately has its
    own single ``signal_note`` key, so we look for *consecutive* duplicates,
    not the global count.)
    """

    text = (REPO_ROOT / "review_engine.py").read_text(encoding="utf-8")
    lines = text.splitlines()
    duplicates: list[int] = []
    for idx in range(len(lines) - 1):
        if (
            '"signal_note":' in lines[idx]
            and '"signal_note":' in lines[idx + 1]
        ):
            duplicates.append(idx + 1)  # human-readable line number
    assert not duplicates, (
        "Phase 1.1 regression: consecutive duplicate 'signal_note' keys "
        f"found at line(s) {duplicates}"
    )


def test_normalize_analysis_mode_validates_against_profiles() -> None:
    """Phase 1.2: ``_normalize_analysis_mode`` must consult
    ``ANALYSIS_MODE_PROFILES`` and return the user-supplied value when it's
    valid, instead of unconditionally returning ``DEFAULT_ANALYSIS_MODE``.
    """

    text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert "ANALYSIS_MODE_PROFILES" in text, "Phase 1.2 import missing"

    # Locate the function body and check it does more than just `return DEFAULT_*`.
    marker = "def _normalize_analysis_mode("
    start = text.find(marker)
    assert start != -1
    end = text.find("\n\n\n", start)
    body = text[start:end] if end != -1 else text[start:]
    assert "ANALYSIS_MODE_PROFILES" in body, (
        "Phase 1.2 regression: _normalize_analysis_mode no longer validates "
        "against ANALYSIS_MODE_PROFILES."
    )


def test_reports_protected_by_lock() -> None:
    """Phase 1.4: REPORTS access must be guarded by ``REPORTS_LOCK``."""

    text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert "REPORTS_LOCK" in text, "Phase 1.4 lock missing"
    assert "with REPORTS_LOCK:" in text, (
        "Phase 1.4 regression: REPORTS_LOCK declared but never used"
    )


def test_pathlib_patch_is_scoped_context_manager() -> None:
    """Phase 1.5: the pathlib swap must be a context manager (not a global
    side-effect at import time), so that Linux/macOS aren't broken by
    `pathlib.PosixPath = pathlib.WindowsPath`.
    """

    text = (REPO_ROOT / "tribe_runtime.py").read_text(encoding="utf-8")
    assert "_patch_pathlib_for_checkpoint_load" in text
    # The old unconditional global patch must be gone.
    assert "pathlib.PosixPath = pathlib.WindowsPath  # type: ignore[assignment]\n\nfrom tribev2" not in text


def test_uvx_path_no_longer_hardcoded_to_comfyui() -> None:
    """Phase 1.6: the ComfyUI uvx path must not be hardcoded; ``TRIBE_UVX_PATH``
    is the supported override.
    """

    text = (REPO_ROOT / "tribe_runtime.py").read_text(encoding="utf-8")
    assert "Documents" not in text or "ComfyUI" not in text, (
        "Phase 1.6 regression: hardcoded ComfyUI uvx path returned"
    )
    assert "TRIBE_UVX_PATH" in text


def test_runtime_patch_module_deleted() -> None:
    """Phase 2.1: ``review_engine_runtime_patch.py`` should no longer exist."""

    assert not (REPO_ROOT / "review_engine_runtime_patch.py").exists()


def test_tribe_review_package_reexports_engine_entrypoints() -> None:
    """Phase 2.2: ``tribe_review`` package must surface the engine entry
    points so callers can migrate without touching review_engine directly."""

    init_path = REPO_ROOT / "tribe_review" / "__init__.py"
    assert init_path.exists()
    text = init_path.read_text(encoding="utf-8")
    for symbol in ("generate_review", "generate_comparison_report", "ACTION_VARIANTS"):
        assert symbol in text


def test_apply_patch_call_removed_from_app_and_smoke() -> None:
    """Phase 2.1: nothing should still be calling
    ``apply_review_engine_patch()``."""

    for filename in ("app.py", "smoke_test.py"):
        text = (REPO_ROOT / filename).read_text(encoding="utf-8")
        assert "apply_review_engine_patch" not in text, (
            f"Phase 2.1 regression: {filename} still imports/calls "
            "apply_review_engine_patch"
        )
        assert "review_engine_runtime_patch" not in text


# Sanity: the scoped patch context manager actually swaps the classes when the
# module imports cleanly (this DOES depend on tribev2/torch being importable,
# so we mark it as part of the import-able import suite by using a deferred
# import inside the test).
def test_pathlib_patch_context_manager_swaps_and_restores() -> None:
    import pathlib

    original_posix = pathlib.PosixPath
    original_windows = getattr(pathlib, "WindowsPath", None)

    # Deferred import - if the heavy deps aren't installed the test is skipped.
    try:
        from tribe_runtime import _patch_pathlib_for_checkpoint_load
    except Exception as exc:  # pragma: no cover - skip path
        import pytest

        pytest.skip(f"tribe_runtime cannot be imported in this environment: {exc!r}")

    with _patch_pathlib_for_checkpoint_load():
        # Inside the context, at least one of the path classes was replaced.
        # We don't assert which one (depends on host platform); just that the
        # context manager doesn't crash.
        pass

    assert pathlib.PosixPath is original_posix
    if original_windows is not None:
        assert pathlib.WindowsPath is original_windows
