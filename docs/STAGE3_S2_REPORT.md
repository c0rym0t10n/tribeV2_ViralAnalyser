# Stage 3 / S2 — Ollama → ES (final report)

PR: `refactor/s2-ollama-es`. Two commits stacked on `main`:

| Commit | What |
|---|---|
| `d03d9dc` (S2) | `ollama_runtime.py` system + user prompts → ES (Mexican coloquial) instructions for the LLM. `ollama_concrete.py` strict-fallback library full RU→ES translation (the path that runs when Ollama is unreachable). `ollama_sanitize.py` dropped the dead RU LLM-output scrubbers (16-tuple RU→RU rewrite list + RU regex normalisations) — the LLM no longer writes RU so they never fired. |
| `(this commit)` | Smoke-test doc + final S2 report. |

**Verification (this sandbox, Windows .venv):**
- `pytest -m "not slow"` → **56 passed**, 1 warning. Engine snapshot tests byte-identical (Ollama is not on the engine code path; goldens unaffected).
- `ruff check .` → **All checks passed.**

## What S2 closes

1. ✅ **LLM prompts in ES.** The `system` and `user` prompts in `simplify_review_copy` now instruct the model to write Spanish (Mexican coloquial), tu-imperativo, EN-preserved TikTok terms, "está" not "es", "video" sin tilde, 8-12-word punchy sentences. Bad / good example phrases flipped to ES so the model has the right tone signal.
2. ✅ **Strict-fallback library in ES.** `ollama_concrete.py` translated end-to-end (3835 → 0 Cyrillic chars). When Ollama is unreachable, `_build_strict_simple_copy` produces the same ES tone the engine path emits.
3. ✅ **Sanitize cleanup.** `ollama_sanitize.py` dropped its RU-output scrubber block (the 16-tuple RU→RU rewrite list, the regex normalisations, the speech-availability replacements branch). `_clean_sentence` keeps the language-agnostic brand-name and "Why:" prefix strips. Cyrillic count: 933 → 22 (defensive `Почему` strips + one comment).

## Cyrillic audit (production code)

Post-S2 production-code Cyrillic count, by file:

| File | Pre-S2 | Post-S2 | Notes |
|---|---|---|---|
| `ollama_runtime.py` | 174 | 6 | The 6 chars are the `Почему` mention inside the prompt ("There must be no field or phrase named 'Why', 'Por qué', or 'Почему'") — kept as a defensive instruction to the LLM. |
| `ollama_concrete.py` | 3835 | 0 | Strict-fallback library fully ES. |
| `ollama_sanitize.py` | 933 | 22 | The 22 chars are the `Почему` strips in `_ACTION_ITEM_INSTRUCTION_REWRITES` + `_clean_sentence` banned-tuple + one legacy comment. Defensive against a Russian-language prefix the LLM might still emit despite the ES prompt. |
| **Total Ollama path** | **4942** | **28** | |

Plus the engine + UI residuals from S1 follow-ups (already at 0 in `tribe_review/*`, `app.py`, `brain_visualization.py`, `pdf_report.py`, `official_report.py`, `analysis_settings.py`, `tests/fixtures/synthetic_run.py`, all 4 goldens).

## What S2 deliberately does NOT close (next stages)

| Surface | Owner |
|---|---|
| `templates/index.html` UI strings (still Russian) | **S3** (frontend ES-first) |
| `_format_error` localized error blocks | done in S1 |
| README / INSTALL_WINDOWS / WORKFLOWS / TROUBLESHOOTING docs | **S4** |
| Final regex sweep `[А-Яа-яЁё]` repo-wide; retire post-hoc EN translation pipeline | **S5** |
| `ACTION_VARIANTS` variety cap (≤3 per metric → repetition between similar videos) | Out of stage stack |

## Smoke-test gate

The S2 smoke is the FIRST one in this PR series where the snapshot suite is genuinely insufficient — both the LLM-rewrite path AND the strict-fallback path live outside the engine. The `docs/STAGE3_S2_SMOKE_TEST.md` doc walks through:

1. **Ollama daemon up + qwen2.5:14b** (or any `PREFERRED_MODELS` entry) → `simplify_review_copy` calls the LLM. Verify `copy_rewrite.provider == "ollama"` and zero Cyrillic in `verdict` / `executive_summary` / `product_summary` / `strengths` / `weaknesses` / `recommendation_plan` / `action_items`.
2. **Ollama daemon down** → `_build_strict_simple_copy` runs. Same Cyrillic gate.
3. **EN parity** (`language="en"` with Ollama up) → expected to leak ES because the post-hoc `localize_report` pipeline still does the EN translation; not a S2 regression.

Decision gate criteria + tone-review checklist live in the smoke doc.

## How the reviewer should read this PR

Suggested order:

1. `d03d9dc` — single S2 commit, three files touched. Read in order:
   1. **ollama_runtime.py** prompts: scan the system + user prompt for tone, EN-term preservation, banned-phrase list.
   2. **ollama_concrete.py** strict-fallback library: `_action_library`, `_action_variant`, `_overall_status`, `_simple_overview_text`, `_simple_banner_text` are the longest blocks. Read out loud for tone.
   3. **ollama_sanitize.py** sanitize cleanup: confirm the dropped 16-tuple isn't going to be missed (it scrubbed RU patterns the LLM no longer emits).
2. Smoke test (`docs/STAGE3_S2_SMOKE_TEST.md`) on `nanogel_tiktokv03.mp4`. **Required gate before merge** — the snapshot suite cannot prove either Ollama path works.

## Push + PR

```
F:\Github-Projects\tribe> git push -u origin refactor/s2-ollama-es
```

Open as draft for CI visibility. After the smoke run (both Ollama-up and Ollama-down paths), mark ready for review.

Stack: G1 ✓ → G2 ✓ → G3 ✓ → G4 ✓ → S1 ✓ → **S2 (closed)** → S3 (frontend ES-first, next).
