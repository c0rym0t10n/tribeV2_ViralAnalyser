# Stage 2 / G4 — ollama_runtime.py audit (honest report)

PR: `refactor/g4-ollama-runtime`. Four commits stacked on `main`.

## Result

| File | Pre-G4 | Post-G4 | Notes |
|---|---|---|---|
| `ollama_runtime.py` | **1031 LOC** | **199 LOC** | Entry point + prompt payload builders + ``get_preferred_model``. Well under the <500 target. |
| `ollama_http.py` | — | 113 LOC | New. HTTP transport + structured-JSON response parsing. |
| `ollama_sanitize.py` | — | 392 LOC | New. Post-LLM cleanup helpers (``_simplify_*``, ``_replace_*``, ``_sanitize_generated_copy``). |
| `ollama_concrete.py` | — | 389 LOC | New. Strict-fallback Russian copy library + builders. |
| **Total** | 1031 | 1093 | +62 LOC across 4 modules — pure docstring + import overhead. |

`pytest -m "not slow"` (Windows .venv): **56 passed, 1 warning**. ``generate_review`` snapshot tests stay byte-identical (Ollama is not on the engine path).

`ruff check .`: **All checks passed.**

## What got cut

### Commit a625199 — `refactor(g4a): extract HTTP plumbing + drop dead translate_text_batch path`
* **Dead code**: `translate_text_batch`, `get_translation_model`, `TRANSLATION_MODELS` had zero callers anywhere in the repo (verified by grep across `*.py` / `*.md`). ~75 LOC dropped.
* **HTTP transport** moves to `ollama_http.py`: `_request_json` (renamed `request_json`), `_rewrite_with_ollama` (renamed `rewrite_with_ollama`), `_parse_json_object` (renamed `parse_json_object`), plus the URL/timeout constants. `ollama_runtime` re-imports under the existing private names so the call sites in `simplify_review_copy` are unchanged.
* `OLLAMA_BASE_URL` / `OLLAMA_TIMEOUT_SECONDS` are re-exported with `noqa: F401` for any legacy caller still reaching for `ollama_runtime.OLLAMA_BASE_URL`.

### Commit c088f0f — `refactor(g4b): extract sanitization helpers into ollama_sanitize`
* All post-LLM cleanup helpers move out: `_apply_simple_cleanup` and the `_simplify_metrics` / `_simplify_focus_windows` / `_simplify_action_items` / `_simplify_speech` group, plus the `_replace_*` helpers `simplify_review_copy` uses to merge structured LLM replies, plus `_split_copy_lines` / `_coerce_action_line` / `_short_action_title` / `_clean_sentence` / `_sanitize_generated_copy`.
* `ollama_runtime` re-imports the names `simplify_review_copy` calls. Unused `import re` is dropped.

### Commit a438428 — `refactor(g4c): extract concrete-fallback builders into ollama_concrete`
* The strict-fallback flow (`_build_strict_simple_copy` and the per-metric `_action_library` / `_action_variant` Russian copy tables, plus `_make_action_item`, `_rewrite_focus_windows`, `_build_concrete_*`, `_overall_status`, `_simple_overview_text`, `_simple_banner_text`, `_compact_instruction`, `_format_seconds_for_copy`) moves out.
* `ollama_runtime` keeps the entry point + the Ollama call + the prompt payload builders.

### Commit da7e904 — `style(g4): drop tribe_review/_engine.py from E501 ignore`
* `_engine.py` had two long lines in the `generate_review` return dict (function calls). Split them across multiple argument lines, no behaviour change. Removed the per-file ignore; `tribe_review/_engine.py` is now ruff-clean without the exemption.

## What deliberately did NOT get cut

1. **The LLM `system` / `user` prompts inside `simplify_review_copy`.** Six long lines (~120-150 chars each) of English instructions to the model. The Stage-2 plan accepted "hardcoded prompt/persona strings → report_localization keyed by language" as a stretch goal, but:
   * There is only one supported LLM language path today (the model produces RU output).
   * The system prompt is one chunk of English meta-instruction, not user-visible copy. Localising it would be premature.
   * Moving it would not bring `ollama_runtime` closer to <500 LOC — we are already at 199.
   * Ergonomically, prompt + payload builder + entrypoint living together makes the call easier to understand. Splitting prompt out into a third module would be over-engineering at this size.

2. **Consolidating `ollama_concrete._action_library` / `_action_variant` with `report_localization._native_action_library_en` / `_native_action_variant_en`.** Today the RU and EN versions of the same tables live in two different files. Merging them into a single `ACTION_LIBRARY_{RU,EN}` pair next to the rest of the localised copy would be cleaner. Not done in G4 — flagged in the `ollama_concrete` module docstring as a follow-up.

3. **Threading `language` through `simplify_review_copy`.** Out of scope: this PR only moves things around. The Ollama path is RU-only by current design (the LLM's system prompt explicitly tells it to write Russian).

## E501 ignore — what came off the list

Pre-G4 `[lint.per-file-ignores]` had:
```
"tribe_review/_engine.py" = ["E501"]
"tribe_review/copy_ru.py" = ["E501"]
"tribe_review/timeline.py" = ["E501"]
"tribe_review/recommendations.py" = ["E501"]
"tribe_review/comparison.py" = ["E501"]
"report_localization.py" = ["E501"]
"ollama_runtime.py" = ["E501"]
"analysis_settings.py" = ["E501"]
"pdf_report.py" = ["E501"]
"official_report.py" = ["E501"]
"brain_visualization.py" = ["E501"]
```

Post-G4:
```
"tribe_review/copy_ru.py" = ["E501"]
"tribe_review/timeline.py" = ["E501"]
"tribe_review/recommendations.py" = ["E501"]
"tribe_review/comparison.py" = ["E501"]
"report_localization.py" = ["E501"]
"ollama_runtime.py" = ["E501"]
"ollama_sanitize.py" = ["E501"]
"ollama_concrete.py" = ["E501"]
"analysis_settings.py" = ["E501"]
"pdf_report.py" = ["E501"]
"official_report.py" = ["E501"]
"brain_visualization.py" = ["E501"]
```

* **Removed**: `tribe_review/_engine.py` (was on the list pre-G4 and after G3; the two long function-call lines split cleanly, now ruff-clean without the exemption).
* **Added**: `ollama_sanitize.py`, `ollama_concrete.py` — these inherit the Russian prose strings the original `ollama_runtime` carried, so the ignore moves with the content.

`ollama_runtime.py` itself stays on the list: 6 long English lines remain (4 in the LLM system prompt + 2 in the `metric_definitions` dict inside `_build_review_prompt_payload`). They are intentionally long so the prompt the LLM sees stays one logical phrase per line.

## Where the real techo is

The PR brings `ollama_runtime.py` to **199 LOC**, which is the file the user asked to measure. Below that floor is essentially:
* The entry point (`simplify_review_copy`, ~90 LOC including the system prompt).
* `_speech_prompt_payload` + `_build_review_prompt_payload` (~70 LOC of structured-payload boilerplate).
* `get_preferred_model` (~20 LOC) + imports + `PREFERRED_MODELS` constant.

Short of moving the prompt body to `report_localization.py` (premature; see above) or hoisting `_build_review_prompt_payload` into its own `ollama_prompts.py` (cosmetic, makes the entry-point file harder to read), there is not much more to cut without churn-for-its-own-sake.

The plan accepted ~700 LOC as a reasonable techo. We came in at 199.

## What this PR does NOT touch

* Goldens. Ollama is not on `generate_review`'s code path; the synthetic snapshot tests in `tests/test_golden_snapshots.py` exercise the engine, not the LLM rewrite. The 56-passing pytest run includes the three RU snapshot tests + the EN one and they stay byte-identical to G3's baseline.
* `app.py`. The only public surface `app.py` consumes is `from ollama_runtime import simplify_review_copy`, which is unchanged.
* The post-hoc `localize_report` pipeline in `report_localization.py`. That path was not on G4's surface.

## Smoke-test note (manual, user-side)

The synthetic tests cover the engine. They do NOT cover the Ollama rewrite path — that path requires a live local Ollama daemon. Before merging this PR, the user should:

1. Start the local Ollama server with one of the `PREFERRED_MODELS` loaded.
2. Run a simplified-mode review through the production app on a real video.
3. Verify the response shape (the `copy_rewrite` field, the rewritten `executive_summary` / `product_summary` / `verdict`, the strengths/weaknesses lists, the recommendation_plan) matches what the same video produced before G4.

If the rewritten payload diverges, the regression is in the import/re-export plumbing — the underlying call site logic is unchanged. The honest expectation is that the diff is empty or limited to LLM nondeterminism (which is unrelated to this PR).
