# Stage 3 / S1 — RU → ES (México coloquial), EN secondary (final report)

PR: `refactor/s1-es-primary`. Eleven commits stacked on `main`.

| Commit | What |
|---|---|
| `3af5e19` (S1-1) | Engine prose RU → ES across `tribe_review/copy_es.py` (renamed from `copy_ru.py`), `timeline.py`, `recommendations.py`, `comparison.py`, `_engine.py`, `__init__.py`, `metrics.py` import, `analysis_settings.py` profile copy. ~250 strings translated. |
| `2b301e1` (S1-2) | `report_localization.py` ES band tables (`METRIC_SUMMARY_LIBRARY_ES`, `SPEECH_SUMMARY_LIBRARY_ES`, `UI_TEXTS["es"]`, `ANALYSIS_MODE_TEXTS["es"]`); API defaults flipped (`DEFAULT_REPORT_LANGUAGE = "es"`, `SUPPORTED_REPORT_LANGUAGES = ("es", "en")`); goldens regenerated. |
| `8ba3d16` (S1-3a) | `ACTION_VARIANTS_ES` (~150 strings), `CURVE_*_ES` constants. Drops every `*_RU` table from `report_localization.py`. `metric_band_summary` / `speech_metric_summary` lose RU dispatch. `LABEL_MAP_EN` population retrained ES-keyed. `tribe_review/copy_es.py` alias flipped to `ACTION_VARIANTS_ES`. `tribe_review/curve_alignment.py` imports `*_ES`. `tests/test_followup_f3_i18n.py` rewritten ES-aware. |
| `2f00524` (S1-3b) | `ollama_sanitize._simplify_*` helpers now read `review["language"]` and dispatch ES / EN; simplified-mode metric labels stay EN jargon (`Hook` / `Retention` / `Pacing` / `Visual clarity` / `Visual punch`). |
| `9e940e5` | Scrub residual Cyrillic the prior commits left behind: `curve_alignment.py:297` ("Подозрительный момент" → "Momento sospechoso", live JSON leak), title-matching sets in `curve_alignment` + `recommendations.py` re-keyed ES, `synthetic_run.py` sample text ES, `report_localization.py` `METRIC_LABELS` + `LABEL_MAP_EN` re-keyed RU → ES end-to-end, `ollama_sanitize.py` normalize tables stripped of RU keys. |
| `869c756` | `app.py` `_format_error` four error blocks (Chrome / Whisper / CUDA / LLaMA gate) translated RU → ES. `language == "ru"` → `language == "es"`. Test in `test_phase4_regressions` still passes (asserts variable-name substrings, not prose). |
| `a762208` | `brain_visualization.py` per-region `label_ru` / `description_ru` / `title_ru` / `hint_ru` keys renamed to `_es` and values translated. Two consumer reads in `templates/index.html` updated to read the `_es` keys. |
| `42330fd` | `pdf_report.py` ~32 RU strings translated to ES (compare-page, summary-page, recommendations-page, details-page, axis labels, meta cards, "How to read it" notes). Five `report.get("report_language", "ru")` defaults flipped to `"es"`. |
| `2495036` | `official_report.py` eight `_<name>_ru` helpers renamed to `_es` and prose translated. `simple_readout` / `practical_readout` dict keys flipped from `"ru"` to `"es"`. Card titles, phase-state strings, fix-card and next-test-card prose all in ES. |
| `fc57376` (S1-4) | Smoke-test doc + interim S1 report. |
| `(this commit)` | Final report — close-out. |

**Verification (this sandbox, Windows .venv):**
- `pytest -m "not slow"` → **56 passed**, 1 warning. Snapshot tests cover deep-ES + simplified-ES + comparison-ES + deep-EN.
- `ruff check .` → **All checks passed.**

## Smoke-test gate (goldens)

```
golden_comparison.json:           clean
golden_review_deep.json:          clean
golden_review_deep_en.json:       clean
golden_review_simplified.json:    clean
```

The agreed Cyrillic-leak detector regex `[Ѐ-ӿ]+` returns zero matches on every regenerated golden. The engine path produces ES end-to-end for `language="es"` and EN end-to-end for `language="en"`.

## Cyrillic still in source (deliberate, NOT engine path)

| File | Chars | Owner |
|---|---|---|
| `ollama_concrete.py` | 3835 | **S2** — strict-fallback Russian copy library. Activates when Ollama is unavailable AND simplified mode is selected. |
| `ollama_runtime.py` | 174 | **S2** — the LLM `system` prompt still tells the model to write Russian. Flipping the prompt to ES is the first task of S2. |
| `ollama_sanitize.py` | 933 | **S2** — `_sanitize_generated_copy` RU-pattern banned-phrases list and RU-rewrite tuples. Active until S2 retires them with the prompt flip. |
| `report_localization.py` | 465 | **S5** — defensive RU-substring matchers in the post-hoc EN translation pipeline (`_native_action_*`, `_apply_known_labels` keyword arrays). Dead code on the engine path; cleaning them is the S5 sweep's job. |
| `templates/index.html` | 2475 | **S3** — frontend ES-first pass. The four key reads tied to `brain_region_panel` / region-list iterators got the `_es` rename in this PR; the rest of the template strings move in S3. |

## Smoke-test caveat for the user

When you run the smoke (`docs/STAGE3_S1_SMOKE_TEST.md`):

- **Deep mode + ES**: ✅ expected RU-clean.
- **Deep mode + EN**: ✅ banded summaries flip to EN; the rest of the prose stays ES (the `localize_report` post-hoc translator still does the heavy lifting for EN).
- **Simplified mode WITHOUT Ollama daemon**: ⚠️ `_build_strict_simple_copy` from `ollama_concrete.py` runs and emits Russian action-item titles + instructions. **This is S2's explicit scope** per the original stage plan — don't merge S1 if you consider this a regression; otherwise it's an expected residual.
- **Simplified mode WITH Ollama daemon**: ⚠️ The LLM still writes Russian (its system prompt instructs it to). The merge happens after `_build_strict_simple_copy` so the LLM output overlays the strict-fallback fields. Cyrillic gate **will fail** here. **S2** flips the prompt and retires the RU-output scrubbers in `ollama_sanitize` together.

If the smoke run finds RU outside those two paths, S1 has missed something — flag it and we patch in a follow-up commit.

## Tone observations from the translation pass

Decisions worth flagging so the diff reads with intent:

- **Bache vs bajón.** *Bache* = sustained-low region (focus window labelled `Bache`, drop-marker label `Momento sospechoso`). *Bajón* = punctual sharp drop ("hay bajones bruscos", `stability` metric label). Different concepts, different vocabulary.
- **Tramo fuerte / Tramo flojo.** Used as nouns; never adjectivised mid-sentence.
- **"Lo que jala" / "Lo que estorba"** for strengths / weaknesses (UI labels): coloquial-creator register, not formal `Fortalezas` / `Debilidades`.
- **"De volada"** is used sparingly. The smoke-test checklist says it should appear at most 1-2 times per full report.
- **"está" vs "es"**: applied to edit-quality state ("el cut está flojo", "la curva está pareja"); inherent properties stay `es`.
- **EN-preserved terms confirmed in goldens:** `hook`, `cut`, `shot`, `frame`, `beat`, `payoff`, `caption`, `B-roll`, `opening`, `CTA`, `retention`, `drop-off`. Plus `wide shot`, `close-up`, `match-cut`, `push-in` where they read naturally.
- **Simplified-mode metric labels** are always EN jargon: `Hook` / `Retention` / `Pacing` / `Visual clarity` / `Visual punch`. Even on `language="es"` reports.
- **Product / brand names** (TRIBE, Whisper, Ollama, ASR, NVIDIA, PyTorch, CUDA, GPU, CPU, Hugging Face, LLaMA, WhisperX, Chrome, Edge, Chromium) keep original case throughout.
- **"video" sin tilde** (México registro).

## ACTION_VARIANTS variety (out of S1 scope, flagged TODO)

User-flagged in the prep convo: `ACTION_VARIANTS_ES` caps at 5-10 variants per metric depending on the key. Two videos that share the same weak-metric ranking will produce identical action-item titles. The fix is a refactor of the selection logic (round-robin against context hash, or carousel by drop-timestamp) and lives outside the language stack entirely. Tracking as a separate Stage-3 task.

## How the reviewer should read this PR

Suggested order:

1. `9e940e5` — clean residuals (`curve_alignment`, `recommendations`, `report_localization` METRIC_LABELS / LABEL_MAP_EN, `ollama_sanitize` normalize, `synthetic_run`). Mostly mechanical re-keying.
2. `8ba3d16` — `ACTION_VARIANTS_ES` is the largest single translation. Read the bodies for tone.
3. `3af5e19` — engine prose. The `verdict` / `executive summary` / `recommendations` candidates are where the tone has to land.
4. `2495036`, `42330fd`, `869c756`, `a762208` — user-facing rendering layer (PDF, official_report, error messages, brain panel). Mechanical translations with consistent tone.
5. `2f00524` — sanitize bug fix.
6. Smoke test (`docs/STAGE3_S1_SMOKE_TEST.md`) on `nanogel_tiktokv03.mp4`. **Required gate before merge.** Run deep mode for the strict gate; simplified mode is expected to leak RU until S2.

## Push + PR

```
F:\Github-Projects\tribe> git push origin refactor/s1-es-primary
```

PR #14 is already open as draft. After the smoke-gate run (deep mode), mark ready for review.

Stack: G1 ✓ → G2 ✓ → G3 ✓ → G4 ✓ → **S1 (closed)** → S2 (Ollama prompts → ES + `ollama_concrete` translation, next).
