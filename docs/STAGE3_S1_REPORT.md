# Stage 3 / S1 — RU → ES (México coloquial), EN secondary (interim report)

PR: `refactor/s1-es-primary`. Two commits landed in this session:

| Commit | What |
|---|---|
| `3af5e19` (S1-1) | Engine prose RU → ES across `tribe_review/copy_es.py` (renamed from `copy_ru.py`), `timeline.py`, `recommendations.py`, `comparison.py`, `_engine.py`, `__init__.py`, `metrics.py` import, `analysis_settings.py` profile copy. |
| `2b301e1` (S1-2) | `report_localization.py` ES band tables (`METRIC_SUMMARY_LIBRARY_ES`, `SPEECH_SUMMARY_LIBRARY_ES`, `UI_TEXTS["es"]`, `ANALYSIS_MODE_TEXTS["es"]`); API defaults flipped (`DEFAULT_REPORT_LANGUAGE = "es"`, `SUPPORTED_REPORT_LANGUAGES = ("es", "en")`); `metric_band_summary` / `speech_metric_summary` default to `"es"`; goldens regenerated end-to-end. Test fixtures + tests updated for new defaults. |

**Verification (Windows .venv):**
- `pytest -m "not slow"` → **56 passed**, 1 warning. Snapshot tests cover deep-ES + simplified-ES + comparison-ES + deep-EN.
- `ruff check .` → **All checks passed.**

## What is NOT yet in this PR — explicit follow-up commits

These three pieces all live in `S1-3` / `S1-4` follow-up commits inside the **same** branch / PR (`refactor/s1-es-primary`). They are flagged in the S1-2 commit message and recorded here so they don't get lost.

### S1-3a — `ACTION_VARIANTS_ES` + drop RU tables

`tribe_review/copy_es.py` currently has a transitional alias:

```python
# TODO(s1-followup): pull from ``ACTION_VARIANTS_ES`` once the ES table lands…
from report_localization import ACTION_VARIANTS_RU as ACTION_VARIANTS  # noqa: F401
```

The follow-up needs to:

1. Add `ACTION_VARIANTS_ES` to `report_localization.py` — ~30 metric-key entries × 2-3 variants × 2 fields (`title`, `instruction`) = ~150 strings of TikTok-creator imperative ES. Keep the same shape as `ACTION_VARIANTS_RU` so existing index-by-variant logic still works.
2. Add `CURVE_FOCUS_WINDOW_LABELS_ES`, `CURVE_FOCUS_WINDOW_SUMMARIES_ES`, `CURVE_DROP_DEFAULT_REASON_ES`, `CURVE_PLAN_TITLE_*_ES` (small, ~10 strings).
3. Flip the `copy_es.py` alias from `ACTION_VARIANTS_RU` to `ACTION_VARIANTS_ES`.
4. Update `get_action_variants()` to default to `"es"`.
5. **Drop the RU tables**: `ACTION_VARIANTS_RU`, `METRIC_SUMMARY_LIBRARY_RU`, `SPEECH_SUMMARY_LIBRARY_RU`, `CURVE_*_RU`, `UI_TEXTS["ru"]`, `ANALYSIS_MODE_TEXTS["ru"]`. Each one cascades into the `_rewrite_english_report` post-hoc translation pipeline (`LABEL_MAP_EN` is RU-keyed today), which needs to either be retrained ES→EN or be deprecated in favour of the engine's native `language="en"` path.
6. Update `test_followup_f3_i18n.py`: replace `ACTION_VARIANTS_RU` references with `ACTION_VARIANTS_ES`, drop the RU sentinel from `test_action_variants_dict_literal_not_reintroduced`.

### S1-3b — `ollama_sanitize._simplify_metrics` bug fix

This is the **explicit user-flagged bug** ("`Темп` leak in simplified+EN JSON") that is **not yet fixed in S1-1/S1-2**. Source: `ollama_sanitize.py`, lines 35-101 of the post-G4-B file. The function rewrites simplified-mode metric labels using a hardcoded RU dict (`key_label_map = {"transition": "Темп", …}`), regardless of the report's `language`.

The fix (planned, not landed):

1. Replace `key_label_map` with the EN-jargon table (`Hook` / `Retention` / `Pacing` / `Visual clarity` / `Visual punch`) — these labels stay EN regardless of `language`, per the agreed tone.
2. Replace the single RU `summary_map` with two parallel maps (ES + EN) keyed by the EN label, dispatched on `review["language"]` (which S1-1 added to the engine output dict).
3. Apply the same pattern to `_simplify_focus_windows`, `_simplify_action_items`, `_simplify_speech` (they all carry RU dicts today and have the same leak shape).
4. Drop the mojibake recovery entries (`"Р В Р В°Р Р…Р Р…Р С‘Р в„– Р С•РЎвЂљР С”Р В»Р С‘Р С”"` etc.) — those were defensive against an old encoding bug that no longer reproduces post-S1.

I drafted the `_simplify_metrics` body in this session but couldn't land it via the chat Edit tool (the multi-line dict-literal block didn't match exact text — likely whitespace drift after the in-session linter pass). Pull it via a small Python migration script in the next pass.

### S1-4 — smoke test docs

S1's `Smoke test crítico` (per the user's plan) needs:

- A doc walking through the manual `nanogel_tiktokv03.mp4` run on the user's Windows machine (parallel to `docs/STAGE2_G3_SMOKE_TEST.md`).
- Decision gate: ES output reads naturally to a creator? Mexicanisms land where intended? EN-preserved terms (hook / cut / shot / frame) untouched?

This is purely a doc commit — no code changes. Can land alongside S1-3.

## Tone observations from this session (for the reviewer)

The translations follow the agreed defaults but a few decision points are worth calling out so the reviewer can read the diff knowing where I committed to one option over another:

- **"Bache" vs "Punto débil" / "Bajón"**: bache is reserved for sustained-low spots in the curve (the focus window). Bajones are punctuation events (short, sharp drops). Both appear in the ES copy at different layers; if the frontend ever puts them on the same card, swap one out per the user's note.
- **"Tramo fuerte" / "Tramo flojo"**: used as nouns; never adjectivised mid-sentence as `tramo fuertísimo` or similar. Stays consistent across the engine.
- **"Lo que jala" / "Lo que estorba"** for strengths/weaknesses (UI labels): coloquial but not cute. Reads naturally in TikTok-creator context. If you want more formal (`Fortalezas` / `Debilidades`), it's a one-line change in `UI_TEXTS["es"]`.
- **"De volada"** is used sparingly, only where the original RU was emphatically immediate. Overuse would make the copy read parodic.
- **"está" vs "es"** rule applied: `"el cut está fuerte"` not `"el cut es fuerte"`. The few exceptions are stylistic (`"la versión jala"` reads better than `"la versión está jalando"`).

## ACTION_VARIANTS variety bug — still TODO out of S1

User-flagged in the prep convo: `ACTION_VARIANTS` caps at 2-3 variants per metric, so two videos that share weak metrics produce identical action-item titles. Refactor lives in a separate Stage-3 task; S5 / cleanup is the natural home for it but it could be its own PR after the language work is done.

## What lands the PR for review

- Push: `git push -u origin refactor/s1-es-primary`
- Open PR base `main`. Mark as **draft** until S1-3 + S1-4 commits land in the branch. The current state passes CI (snapshot tests + ruff) but the smoke test gate is not satisfied yet.
- After S1-3 lands and the user runs the smoke against `nanogel_tiktokv03.mp4`, mark ready for review.
