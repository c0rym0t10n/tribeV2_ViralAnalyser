"""Golden-snapshot tests for ``tribe_review.generate_review`` /
``generate_comparison_report``.

Phase G1 of the Stage-2 refactor: this is the safety net that lets G2 move
function bodies between modules without silently changing behaviour. The
snapshots are captured once with the current engine output and committed to
``tests/fixtures/golden_*.json``. Any later refactor that drifts the output
will show a diff.

Why these tests don't need TRIBE/torch/moviepy
----------------------------------------------
* Synthetic, deterministic numpy-backed stand-ins live in
  ``tests/fixtures/synthetic_run.py`` and provide the exact attribute surface
  the engine reads from ``TribeRunResult`` / ``SpeechRunResult``.
* The engine's only hard dependency on moviepy is ``_read_video_info``; we
  monkeypatch it to a pre-baked dict so the test runs in CI's light tier
  (numpy + matplotlib only).

Updating goldens
----------------
Set ``TRIBE_REVIEW_UPDATE_GOLDENS=1`` and run pytest. The test will rewrite
the JSON fixtures with the engine's current output and pass. Inspect the
diff before committing — that's the whole point of the snapshot.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

# numpy is in the light-tier requirements; if the environment is even
# lighter than that we want a clear skip rather than a spurious failure.
np = pytest.importorskip("numpy")

from tests.fixtures.synthetic_run import (  # noqa: E402  (import after importorskip)
    make_synthetic_speech_run,
    make_synthetic_tribe_run,
    synthetic_video_info,
)
from tribe_review import generate_comparison_report, generate_review  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
UPDATE_FLAG = "TRIBE_REVIEW_UPDATE_GOLDENS"


def _stub_video_info(filename: str = "synthetic.mp4"):
    """Returns a callable that mimics ``_read_video_info`` without moviepy."""

    def _stub(video_path: Any) -> dict[str, Any]:
        del video_path  # we ignore the path entirely in light-tier tests
        return synthetic_video_info(filename=filename)

    return _stub


def _to_jsonable(value: Any) -> Any:
    """Recursively coerce numpy scalars / arrays into JSON-native primitives.

    The engine generally rounds and casts (``round(float(...), n)``) before
    putting values in its output dict, but a couple of paths leak ``np.float64``
    or ``np.int64`` in nested structures. Normalize once here so the JSON
    fixture stays small and human-readable.
    """
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        return value.tolist()  # numpy arrays
    if hasattr(value, "item") and hasattr(value, "dtype"):
        return value.item()  # numpy scalars
    return value


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop / flatten fields that are volatile or dependent on the host.

    The engine's output is mostly stable for fixed inputs, but a few fields
    are content-volatile or carry non-JSON types:

    * Numpy scalars/arrays are cast via ``_to_jsonable``.
    * That's it — there are no ``report_id`` / ``created_at`` / URL fields in
      the engine's output. Those live in ``app.py`` (the web layer) and are
      out of scope for engine snapshots.
    """
    return _to_jsonable(payload)


def _load_or_capture(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Either compare ``payload`` against the on-disk golden, or rewrite the
    golden in update mode."""

    path = FIXTURES_DIR / name
    normalized = _normalize(payload)
    if os.environ.get(UPDATE_FLAG) == "1":
        path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return normalized

    if not path.exists():
        pytest.fail(
            f"Golden fixture {name} is missing. Re-run with "
            f"{UPDATE_FLAG}=1 to capture it, then inspect the diff."
        )

    expected = json.loads(path.read_text(encoding="utf-8"))
    assert normalized == expected, (
        f"Engine output drifted from golden {name}. If the change is intended, "
        f"re-run with {UPDATE_FLAG}=1 and inspect the diff before committing."
    )
    return normalized


def _make_review(monkeypatch: pytest.MonkeyPatch, *, mode: str, variant_name: str, early_strong: bool, seed: int):
    monkeypatch.setattr("tribe_review._engine._read_video_info", _stub_video_info(f"{variant_name}.mp4"))
    return generate_review(
        video_path=f"{variant_name}.mp4",
        run=make_synthetic_tribe_run(early_strong=early_strong, seed=seed),
        speech=make_synthetic_speech_run(),
        speech_error=None,
        analysis_mode=mode,
        variant_name=variant_name,
    )


def test_generate_review_deep_matches_golden(monkeypatch: pytest.MonkeyPatch) -> None:
    review = _make_review(monkeypatch, mode="deep", variant_name="variant_a", early_strong=True, seed=1234)
    _load_or_capture("golden_review_deep.json", review)


def test_generate_review_simplified_matches_golden(monkeypatch: pytest.MonkeyPatch) -> None:
    review = _make_review(monkeypatch, mode="simplified", variant_name="variant_a", early_strong=True, seed=1234)
    _load_or_capture("golden_review_simplified.json", review)


def test_generate_comparison_report_matches_golden(monkeypatch: pytest.MonkeyPatch) -> None:
    review_a = _make_review(monkeypatch, mode="deep", variant_name="variant_a", early_strong=True, seed=1234)
    review_b = _make_review(monkeypatch, mode="deep", variant_name="variant_b", early_strong=False, seed=4321)
    comparison = generate_comparison_report([review_a, review_b], analysis_mode="deep")
    _load_or_capture("golden_comparison.json", comparison)
