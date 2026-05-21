# Stage 3 / S3 — Frontend ES-first (close-out)

**Branch:** `refactor/s3-frontend-es`
**Base:** `main` (includes U1 toggle + U2 env vars)
**Commits:** `3be1d3a` (code) + this doc
**Status:** draft, waiting for visual smoke test (see `STAGE3_S3_SMOKE_TEST.md`).

---

## TL;DR

Hoisted every literal EN/RU string in `templates/index.html` to `UI_TEXTS` lookups. ES is the default; EN is `?lang=en`. RU is gone from the template — no more ternaries that fall to Russian when `language="es"`.

| Metric | Before | After |
|---|---|---|
| Cyrillic chars in `templates/index.html` | 2505 | **0** |
| EN/RU ternaries in template | 69 | **2** (DB-backed `brain_region_panel.*` only) |
| `UI_TEXTS` keys | 47 ES / 47 EN | **104 ES / 104 EN** |
| pytest `-m "not slow"` | 54 passed, 2 skipped | 54 passed, 2 skipped |
| Jinja render with `StrictUndefined` (`lang=es` and `lang=en`) | n/a | both succeed, 0 Cyrillic in output |

---

## What changed (file by file)

### `templates/index.html` (3050 lines)

65 EN/RU ternaries → 65 `{{ ui.<key> }}` lookups. Six lookups reused existing keys (`new_run`, `analysis_mode`, `versions_suffix`, `compare_summary`, `timeline_level`, `timeline_hint`); the other 59 referenced new keys.

Three side-fixes piggy-backed because they were in the same file and would otherwise leak RU:

1. **U1 toggle bug.** `{{ "Deep" if language == "en" else "Глубокий" }}` (and the `Simplified` twin) sent the ES user to Russian. Now `{{ ui.mode_toggle_deep }}` / `{{ ui.mode_toggle_simplified }}` with ES = "A profundidad" / "Simplificado".
2. **`brain_region_panel` fallback dict.** Inside two Jinja `{% set %}` blocks the fallback panel was `{"title_ru": ..., "hint_ru": ...}` but the template reads `.title_es` / `.hint_es` — so the fallback path was effectively dead and rendered `None`. Switched the keys to `_es` and translated the values.
3. **Dead JS in `bindTimeline`.** A check `(label).includes("Р")` (Cyrillic R) used to swap the tooltip label back to a Russian original. Labels are never Russian now; simplified the line to `wrap.dataset.tooltipLabel || responseLabel`.

Also: `В·` mojibake on the report-id chip → proper `·` (U+00B7).

### `report_localization.py`

Added 57 new keys to `UI_TEXTS["es"]` and `UI_TEXTS["en"]`, both inserted right after the existing `no_files_selected` sentinel so the surrounding code keeps working. New keys cover:

- 9 hero card lines (3 cards × 3 lines)
- 5 upload-form lines
- 2 mode-toggle labels (the U1 fix)
- 4 progress / running-state lines
- 1 compare-mode pill
- 1 model disclaimer
- 4 workspace tab labels
- 7 comparison-view labels (overlay, brain map, score, avg, start, workflow note, layout note)
- 7 single-review labels (video, predicted-response title, predicted-brain title + note, etc.)
- 9 prediction-details labels (duration, fps, parts, strongest moment, etc.)
- 4 sources-block labels
- 7 JS-embedded labels (brain 3D errors, zone activity descriptors)

Approach for each key: the ternary's existing EN string became the new `en` value verbatim; the RU branch was translated to ES (Mexican coloquial) preserving EN TikTok terms (`hook`, `cut`, `shot`, `frame`, `timeline`, `overlay`, `brain map`, `B-roll`).

---

## Tone choices

Consistent with S1 and S2:

- **`tú` imperative.** "Lee la curva", "Acciona sobre el cut", "Sube un video", "Mira dónde el video gana...".
- **EN-preserved jargon.** TikTok terms stay in English even in the ES branch: `hook`, `cut`, `shot`, `frame`, `timeline`, `overlay`, `brain map`, `hotspots`, `score`. Plain Spanish where there is no jargon: `curva`, `bajón`, `arranque`, `respuesta predicha`.
- **`está` not `es`.** "Está activa ahorita" / "está más fuerte" — present-state verbs use `estar` because they describe a moment, not an essence.
- **`video` without accent.** Consistent across the whole codebase.
- **Mexicanisms allowed in chips, not in disclaimers.** "ahorita" in JS zone descriptors ("más activa ahorita"); the model disclaimer stays neutral so it doesn't feel jokey on a serious page.

---

## What I did NOT touch (out of scope by design)

- **`report_localization.py` defensive matchers** (465 RU chars across the file). These live in `_normalize_focus_window_label` and `_rewrite_english_report` and scrub legacy LLM output / replay older reports. Per S5 plan, they get retired together with the post-hoc `localize_report` pipeline. Touching them now would risk breaking goldens.
- **The 2 remaining `if language ==` ternaries** in the template (lines 2089–2090). They read `brain_region_panel.title_es` / `.hint_es` from a DB-backed structure that already provides both ES and EN — they cannot move to `UI_TEXTS` without changing the data layer.
- **README / docs.** S4.
- **`ACTION_VARIANTS` variety bug.** Not language-stack; gets its own PR after S5.

---

## Verification trail

1. Cyrillic detector before: `2505` chars across `templates/index.html`. After: `0`.
2. Cyrillic detector on **rendered** output (Jinja2 in a script, both `lang=es` and `lang=en`, `result=None` context): `0` / `0`.
3. Jinja2 `StrictUndefined` render: succeeded for both languages — no missing `ui.*` key.
4. `pytest -m "not slow"`: 54 passed, 2 skipped (`ruff`/`torch` absent in sandbox). No regressions on engine goldens, localization tests, or curve-alignment tests.
5. Diff size: `+186 / -72` over 2 files. Most of the +186 is the new UI_TEXTS entries.

---

## Suggested review order

1. `report_localization.py` — scan the new ES + EN dict entries for tone consistency. Easiest to read by zooming the diff to the `UI_TEXTS` block.
2. Open the rendered ES and EN pages side-by-side (see smoke doc) — visual is faster than reading template diff for layout-heavy changes.
3. Verify the U1 toggle (deep/simplified) shows ES labels when `language=es`, not RU. This was the explicit Cory-flagged bug.
4. Verify the brain panel fallback. Easiest test: run a video where `brain_simulation.region_panel` is None; the panel should still render with ES title + hint.

---

## After merge

- Run the S3 smoke checklist live.
- Mark PR ready, merge into main.
- S4 (README + docs ES) next.
- S5 (RU defensive matcher cleanup, post-hoc pipeline retire, residual `Почему` strips) last.
