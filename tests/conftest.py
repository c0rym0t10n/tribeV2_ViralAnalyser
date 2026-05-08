"""Pytest fixtures for the TRIBE review test suite.

Tests are split into two tiers:

* **Light tier** (default in CI): targets pure-Python modules that have no
  third-party dependencies beyond what `requirements-dev.txt` provides
  (`analysis_settings`, `report_localization`, `pdf_report._find_chrome_executable`).
* **Slow tier** (`@pytest.mark.slow`): full pipeline tests that require the
  TRIBE model checkpoint, torch, and tribev2 to be installed. Run locally with
  `pytest -m slow` after `pip install -r requirements.txt`. Skipped in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is importable when pytest is invoked from a subdirectory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
