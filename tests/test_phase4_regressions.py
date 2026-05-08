"""Static regression checks for Phase 4 cross-platform / UX work."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pdf_endpoint_imports_matplotlib_fallback() -> None:
    """Phase 4.1: ``app.py`` must import ``render_pdf_report`` so the PDF
    endpoint can fall back to matplotlib when Chrome isn't installed."""

    text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert "render_pdf_report" in text
    assert "X-PDF-Renderer" in text


def test_format_error_covers_chrome_whisper_cuda() -> None:
    """Phase 4.3: ``_format_error`` must produce dedicated localized messages
    for Chrome-missing, Whisper / uvx, and CUDA failures (not just the
    LLaMA-gate path)."""

    text = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    assert "is_chrome_missing" in text
    assert "is_whisper_download" in text
    assert "is_cuda_error" in text
    # Both languages should be present for each new branch.
    for snippet in (
        "TRIBE_CHROME_PATH",
        "TRIBE_UVX_PATH",
    ):
        assert snippet in text


def test_readme_documents_env_vars() -> None:
    """Phase 4.2: README must expose the four runtime env vars."""

    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Environment variables" in text
    for var in ("TRIBE_CACHE_DIR", "TRIBE_CHROME_PATH", "TRIBE_UVX_PATH", "TRIBE_ENABLE_TEXT_EVENTS"):
        assert var in text


def test_unix_launcher_present_and_executable_marker() -> None:
    """Phase 4.5: ``start_mvp.sh`` and ``Start_TRIBE_Review.command`` should
    exist with shebangs."""

    sh = REPO_ROOT / "start_mvp.sh"
    cmd = REPO_ROOT / "Start_TRIBE_Review.command"
    assert sh.exists(), "Phase 4.5 missing start_mvp.sh"
    assert cmd.exists(), "Phase 4.5 missing Start_TRIBE_Review.command"
    sh_text = sh.read_text(encoding="utf-8")
    cmd_text = cmd.read_text(encoding="utf-8")
    assert sh_text.startswith("#!/usr/bin/env bash"), "start_mvp.sh missing shebang"
    assert cmd_text.startswith("#!/usr/bin/env bash"), ".command file missing shebang"
    # Sanity: launcher should call uvicorn on port 8000.
    assert "uvicorn" in sh_text
    assert "8000" in sh_text


def test_macos_quickstart_documented() -> None:
    """Phase 4 README should explain the macOS / Linux quickstart path."""

    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Quick start on macOS / Linux" in text or "macOS / Linux" in text
    assert "start_mvp.sh" in text
