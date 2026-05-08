"""Regression tests for Follow-up F5 (re-enable E501)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_ruff_toml_no_longer_globally_ignores_e501() -> None:
    """F5: E501 must be off the top-level ``ignore`` list. Per-file ignores
    in ``[lint.per-file-ignores]`` are fine — those are explicit opt-outs."""

    text = (REPO_ROOT / "ruff.toml").read_text(encoding="utf-8")

    # Find the top-level lint.ignore list and verify E501 is not in it.
    # We do this with a simple scan instead of a TOML parser to avoid the
    # extra dev-dep (tomli is stdlib only on 3.11+ and ruff.toml lives
    # outside of pyproject anyway).
    in_lint_section = False
    ignore_line: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        # Ignore per-file-ignores subsection — those are explicit opt-outs.
        if line.startswith("[lint.per-file-ignores]"):
            in_lint_section = False
            continue
        if line.startswith("[lint]"):
            in_lint_section = True
            continue
        if line.startswith("["):
            in_lint_section = False
            continue
        if in_lint_section and line.startswith("ignore"):
            ignore_line = line
            break

    assert ignore_line is not None, "ruff.toml is missing a top-level [lint] ignore line"
    assert "E501" not in ignore_line, (
        "F5 regression: E501 is still in ruff.toml's global ignore list. "
        f"Line: {ignore_line!r}"
    )
    assert "F601" in ignore_line and "F541" in ignore_line, (
        "F5 regression: F601/F541 (the original pre-existing exclusions) "
        "should remain in the global ignore until they are individually "
        "fixed."
    )


def test_ruff_toml_has_line_length_setting() -> None:
    text = (REPO_ROOT / "ruff.toml").read_text(encoding="utf-8")
    assert "line-length" in text, "F5 regression: explicit line-length setting missing"


def test_ruff_check_clean() -> None:
    """Final smoke: invoke ruff (if installed) and assert it exits 0.

    Skipped silently when ruff isn't installed - CI installs it from
    requirements-dev.txt, but local dev environments may not.
    """

    import shutil
    import subprocess
    import sys

    if shutil.which("ruff") is None:
        try:
            import ruff  # noqa: F401
        except ImportError:
            import pytest

            pytest.skip("ruff not available in this environment")

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "F5 regression: `ruff check .` failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
