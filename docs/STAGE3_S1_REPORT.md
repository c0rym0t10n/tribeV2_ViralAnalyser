# Stage 3 / S1 — RU → ES (México coloquial), EN secondary (final report)

PR: `refactor/s1-es-primary`. Five commits stacked on `main`.

| Commit | What |
|---|---|
| `3af5e19` (S1-1) | Engine prose RU → ES across `tribe_review/copy_es.py` (renamed from `copy_ru.py`), `timeline.py`, `recommendations.py`, `comparison.py`, `_engine.py`, `__init__.py`, `metrics.py` import, `analysis_settings.py` profile copy. ~250 strings translated. |
| `2b301e1` (S1-2) | `report_localization.py` ES band tables (`METRIC_SUMMARY_LIBRARY_ES`, `SPEECH_SUMMARY_LIBRARY_ES`, `UI_TEXTS["es"]`, `ANALYSIS_MODE_TEXTS["es"]`); API defaults flipped (`DEFAULT_REPORT_LANGUAGE = "es"`, `SUPPORTED_REPORT_LANGUAGES = ("es", "en")`); goldens regenerated. ~100 strings. |
| `8ba3d16` (S1-3a) | `ACTION_VARIANTS_ES` (~150 strings, parallel shape to EN), `CURVE_*_ES` constants. Drops every `*_RU` table from `report_localization.py`. `metric_band_summary` / `speech_metric_summary` lose RU dispatch. `LABEL_MAP_EN` population retrained ES-keyed. `tribe_review/copy_es.py` alias flipped to `ACTION_VARIANTS_ES`. `tribe_review/curve_alignment.py` imports `*_ES`. `tests/test_followup_f3_i18n.py` rewritten ES-aware. Goldens regenerated end-to-end. |
| `2f00524` (S1-3b) | Fix the explicit user-flagged bug: `ollama_sanitize._simplify_*` helpers leaked RU labels (`Темп`, `Хук`…) regardless of report language. All five helpers now read `review["language"]` and dispatch ES / EN; simplified-mode metric labels stay EN jargon (`Hook` / `Retention` / `Pacing` / `Visual clarity` / `Visual punch`) per the agreed tone. |
| `(this commit)` (S1-4) | `docs/STAGE3_S1_SMOKE_TEST.md` and this report. |

**Verification (this sandbox, Windows .venv):**
- `pytest -m "not slow"` → **56 passed**, 1 warning. Snapshot tests cover deep-ES + simplified-ES + comparison-ES + deep-EN.
- `ruff check .` → **All checks passed.**

## What S1 closes

1. ✅ **Engine prose end-to-end ES.** Every helper that emits user-visible prose (verdict, executive summary, product summary, strengths, weaknesses, recommendations, recommendation plan, focus windows, drop reasons, phase notes, speech-layer notes, comparison verdicts, axis winners, common gaps, ranking summaries) now produces Spanish. Searching the engine modules for `[А-Яа-яЁё]` returns zero hits in production code paths.
2. ✅ **`ACTION_VARIANTS_ES` is the canonical action-item catalogue.** No more RU stop-gap alias in `copy_es.py`. The post-hoc EN translation pipeline (`LABEL_MAP_EN`) is retrained to ES-keyed so `localize_report(report, "en")` still produces English.
3. ✅ **Ollama-rewrite RU leak bug fixed.** Simplified-mode reports no longer emit `Темп` / `Хук` / `Чистота кадра`. Mojibake-recovery entries dropped (the encoding bug they defended doesn't reproduce post-S1).
4. ✅ **Defaults flipped.** `DEFAULT_REPORT_LANGUAGE = "es"`, `SUPPORTED_REPORT_LANGUAGES = ("es", "en")`. Tests and goldens follow.
5. ✅ **Smoke-test doc** with explicit Cyrillic-leak detector + tone checklist + Ollama path verification.

## What S1 deliberately does NOT close (next stages)

| Surface | Owner |
|---|---|
| `templates/index.html` UI strings (still Russian) | **S3** (frontend ES-first) |
| Ollama LLM prompts in `ollama_runtime.simplify_review_copy` (still English meta-instructing the model to write Russian) | **S2** (Ollama → ES) |
| Strict-fallback library in `ollama_concrete._action_library` / `_action_variant` (still RU) | **S2** |
| `_format_error` messages in `app.py` (Chrome / Whisper / CUDA, still EN/RU) | **S4** |
| `README.md`, `docs/INSTALL_WINDOWS.md`, `docs/WORKFLOWS.md`, `docs/TROUBLESHOOTING.md` (still RU) | **S4** |
| Final regex sweep `[А-Яа-яЁё]` repo-wide | **S5** |
| `ACTION_VARIANTS` variety cap (≤3 per metric → action-item template repetition between similar videos) | Out of stage stack — own PR |

## Tone observations from the translation pass (for the reviewer)

Decisions worth flagging so the diff reads with intent:

- **Bache vs bajón.** *Bache* = sustained-low region (focus window labelled `Bache`). *Bajón* = punctual sharp drop ("hay bajones bruscos", `stability` metric label). Both appear at different layers; if the frontend ever puts them on the same card, swap one out per the user's note in the planning thread.
- **Tramo fuerte / Tramo flojo.** Used as nouns; never adjectivised mid-sentence. Stays consistent across the engine and the focus-window labels.
- **"Lo que jala" / "Lo que estorba"** for strengths / weaknesses (UI labels in `UI_TEXTS["es"]`): coloquial-creator register, not formal `Fortalezas` / `Debilidades`. If the reviewer prefers formal, it's a one-line UI string change.
- **"De volada"** is used sparingly. The smoke-test checklist explicitly says it should appear at most 1-2 times per full report; overuse reads parodic.
- **"está" vs "es"** rule applied: edit quality is a state ("el cut está flojo"), not an inherent property ("el cut es flojo"). The few exceptions are stylistic where `está` reads worse than the alternative.
- **EN-preserved terms confirmed in goldens:** `hook`, `cut`, `shot`, `frame`, `beat`, `payoff`, `caption`, `B-roll`, `opening`, `CTA`, `retention`, `drop-off`. The script never wraps these in quotes or italics — they read as natural creator vocabulary.
- **Simplified-mode metric labels** are always EN jargon: `Hook` / `Retention` / `Pacing` / `Visual clarity` / `Visual punch`. Even on `language="es"` reports. This is the explicit tone agreement (point 4 of the kickoff).

## ACTION_VARIANTS variety (out of S1 scope, flagged TODO)

User-flagged in the prep convo: `ACTION_VARIANTS_ES` caps at 5-10 variants per metric depending on the key. Two videos that share the same weak-metric ranking will produce identical action-item titles. The fix is a refactor of the selection logic (round-robin against context hash, or carousel by drop-timestamp) and lives outside the language stack entirely. Tracking as a separate Stage-3 task.

## How the reviewer should read this PR

Suggested order:

1. `8ba3d16` — `report_localization.py` is the biggest diff but the most mechanical (one big block of ES translations parallel to the existing EN). Scan for tone, not structure.
2. `3af5e19` — engine prose. Read the `verdict` / `executive summary` / `recommendations` candidates out loud. This is where the tone has to land.
3. `2f00524` — sanitize bug fix. Verify `_apply_simple_cleanup` reads `review["language"]` and threads it; verify all five helpers got their RU dicts removed.
4. `2b301e1` — small. Adds ES tables alongside RU/EN; flips defaults.
5. Smoke test (`docs/STAGE3_S1_SMOKE_TEST.md`) on the user's machine with `nanogel_tiktokv03.mp4`. **Required gate before merge.**

## Push + PR

```
F:\Github-Projects\tribe> git push -u origin refactor/s1-es-primary
```

Open as **draft** for CI visibility. Mark ready for review after the user-side smoke test passes the Cyrillic gate + tone checklist.

Stack: G1 ✓ → G2 ✓ → G3 ✓ → G4 ✓ → **S1 (closed)** → S2 (Ollama → ES, next).
