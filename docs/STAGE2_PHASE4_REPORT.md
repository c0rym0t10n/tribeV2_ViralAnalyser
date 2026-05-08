# Stage 2 — Phase 4 (honest report)

Status as of `2026-05-08` on this session. Stack: G1 → G2 → G3 → G4.

## TL;DR

| PR | Branch | Status | CI light tier | Notes |
|----|--------|--------|---------------|-------|
| G1 | `refactor/g1-golden-snapshots` (commit `d489122`) | **Done** | 53 passed, 2 skipped (torch / ruff) | Pushable as PR against `main`. |
| G2 | — | **Not started** | — | Plan + risk notes below. |
| G3 | — | **Not started** | — | Blocked by G2. |
| G4 | — | **Not started** | — | Independent of G2/G3 but needs its own audit pass. |

CI script (`.github/workflows/ci.yml`) already runs `pytest -m "not slow"` against `numpy + matplotlib`, which is exactly what G1 needs — no workflow changes were required.

## G1 — what shipped

**Commit:** `d489122 test(g1): golden snapshot tests for generate_review / generate_comparison_report`

### Files
- `tribe_review/_engine.py` — gated heavy imports.
  - `from speech_runtime import SpeechRunResult` and `from tribe_runtime import TribeRunResult` moved under `if TYPE_CHECKING:`. With `from __future__ import annotations` already in place, the runtime references are strings, so this is safe.
  - `import moviepy as mpy` → lazy import inside `_read_video_info`. The engine no longer requires moviepy/torch/whisper/tribev2 at import time.
- `tests/fixtures/synthetic_run.py` — small numpy-backed dataclasses (`SyntheticTribeRun`, `SyntheticSpeechRun`, `SyntheticWord`, `SyntheticSegment`) plus factories. Deterministic via numpy seed, default 8 timestamps × 4 features. `early_strong=False` flips the envelope so two variants generate distinct comparison metrics.
- `tests/fixtures/golden_review_deep.json` (297 lines), `golden_review_simplified.json` (297 lines), `golden_comparison.json` (838 lines) — captured engine output. Regenerable with `TRIBE_REVIEW_UPDATE_GOLDENS=1 pytest tests/test_golden_snapshots.py`.
- `tests/test_golden_snapshots.py` — three tests, each monkeypatches `tribe_review._engine._read_video_info` to a pre-baked dict and compares engine output against the JSON golden. Numpy-only; no torch / moviepy / tribev2 required.

### Side effect
The two tests in `tests/test_followup_f3_i18n.py` that previously **skipped** with `ModuleNotFoundError("No module named 'moviepy'")` now **pass**. That's expected — the engine is now importable in the light tier — but worth flagging so the reviewer doesn't read it as a regression.

### What I deliberately did NOT do in G1
- No body moves between modules (that's G2).
- No ruff/lint changes — `ruff` isn't installed in the test sandbox; relying on CI's lint job.
- No CI workflow edits — current `ci.yml` already covers the new tests.

### Verification
```
PYTHONPYCACHEPREFIX=/tmp/pyc_g1 python3 -B -m pytest -v -m "not slow"
# 53 passed, 2 skipped in 1.59s
```

The two skips are the pre-existing ones (`tribe_runtime` needs torch, `ruff` not installed in sandbox), unrelated to this PR.

## G2 — not started; plan + risks

### Target end-state
- `_engine.py` keeps **only** the orchestrators (`generate_review`, `generate_comparison_report`) plus the dataclasses that everyone else imports cleanly.
- Function bodies live in:
  - `metrics.py` — dataclasses, score math, signal-shape helpers, video info reader.
  - `recommendations.py` — verdict, strengths, weaknesses, recommendations, action items.
  - `comparison.py` — multi-variant comparison + `generate_comparison_report` itself.
  - `timeline.py` — timeline build, focus windows, drop moments, speech layer.
  - `copy_ru.py` — Russian copy strings + tiny helpers (`_metric_label`, `_metric_summary`, `_signal_note`, `_score_bucket`, the per-metric `_*_summary` functions).
- `tribe_review/__init__.py` keeps the public surface (already lists the right names).

### Suggested move order (to avoid circular imports)
1. **`copy_ru.py`** (leaf — pure strings/helpers, no engine imports).
2. **`metrics.py`** (depends on `copy_ru` only).
3. **`timeline.py`** and **`recommendations.py`** (both depend on `metrics` + `copy_ru`).
4. **`comparison.py`** (depends on `metrics` + `copy_ru` + the comparison-only helpers).
5. **`_engine.py`** becomes the orchestrator and imports from all of the above.

### Risks
- **CRLF / Edit-tool corruption.** During this session the Edit tool truncated `_engine.py` (size dropped from 1237 → 1226 lines, ending mid-statement) when applied across the CRLF-encoded file. I had to restore from `git show HEAD` and re-apply the edit via a Python script that wrote LF explicitly. **Recommendation for G2:** do the body moves with a single Python migration script that reads the source as text, slices function blocks by AST or regex, and writes the targets with `newline="\n"`. Don't drive G2 through the chat Edit tool against the CRLF working tree.
- **`__init__.py` re-export drift.** Today the thematic stubs re-export from `_engine`. After G2 the direction flips — `_engine` re-exports from the thematics for the public surface (`generate_review`, `generate_comparison_report`, dataclasses). Make sure `tribe_review/__init__.py` still resolves so `from tribe_review import generate_review` keeps working; the existing test `test_tribe_review_package_reexports_engine_entrypoints` will catch a regression here.
- **Goldens are the safety net.** G2 must not change behaviour. Run `pytest tests/test_golden_snapshots.py` after each move; if a single byte drifts, the move was lossy.
- **Stale `__pycache__`.** The Windows-side `.pyc` files can't be deleted from the Linux mount (permission denied). Use `PYTHONPYCACHEPREFIX=/tmp/...` or `python -B` when sanity-checking imports, or have the user clear `__pycache__` from Windows.

## G3 — not started

Plan as written: scan `_engine.py` (and the post-G2 modules) for `if score >= N: text` ladders, key the strings on `(metric_key, score_band, language)` inside `report_localization.py`, and have the engine call `localize.copy_for_band(metric_key, score)`.

Concrete inventory candidates the audit identified — all currently inline in `_engine.py`, lines ~486–523:
`_early_response_summary`, `_sustain_summary`, `_transition_summary`, `_stability_summary`, `_density_summary`, `_speech_start_summary`, `_speech_pace_summary`, `_articulation_summary`, `_pause_summary`, `_confidence_summary`. Each is a single ternary chain with three buckets (≥75 / ≥60 / else for score-based; bespoke thresholds for speech-based).

After G3, the goldens for `analysis_mode="deep"` AND `analysis_mode="simplified"` need to be regenerated and inspected. The plan says we should also be able to drive a `lang="en"` golden — that requires the engine to take a language parameter (it currently doesn't; `report_localization.get_ui_texts` exists but isn't threaded into `generate_review`). That threading is a non-trivial signature change and should be its own commit inside G3.

## G4 — not started

`ollama_runtime.py` is **57,499 bytes** today (post-F4 dead-code drop). Eyeballing, that's roughly 1,500 LOC; the <500 target means cutting two-thirds.

Without a dedicated audit pass I can't say where the techo is, but the obvious extraction candidates are:
- All hardcoded prompt / persona strings → `report_localization.py` keyed by language.
- Any HTTP / streaming plumbing that doesn't depend on Ollama specifics → its own module (`http_helpers.py`?).
- Repeated request-builder boilerplate → a single helper.

If the result of an honest audit is "we can land at ~700 LOC, not 500, without breaking the public surface", the plan explicitly accepts that as long as we document the techo. So G4's deliverable is *either* `<500 LOC` *or* `a written justification of where the floor is`.

## What the reviewer should look at first on G1

1. `tribe_review/_engine.py` diff: confirm only the two import blocks changed.
2. `tests/fixtures/synthetic_run.py`: confirm the attribute surface matches what `_engine.py` actually reads from `TribeRunResult` / `SpeechRunResult`. (The module docstring lists these explicitly.)
3. `tests/test_golden_snapshots.py`: confirm the monkeypatch target (`tribe_review._engine._read_video_info`) is correct and that the goldens cover both modes + comparison.
4. The three JSON goldens: skim for obviously-wrong content (empty fields, leaked numpy reprs). I scanned them and they look like real engine output.
