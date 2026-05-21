# Stage 3 / S3 — Frontend ES-first smoke test

**Branch:** `refactor/s3-frontend-es` (commit `3be1d3a`)
**Scope:** `templates/index.html` + new `UI_TEXTS` keys in `report_localization.py`. No engine, no Ollama, no PDF.
**Status:** draft PR until this smoke passes.

---

## What S3 changed

- **65 EN/RU ternary expressions** in `templates/index.html` replaced with `{{ ui.<key> }}` lookups. The EN branch went to the new `UI_TEXTS["en"][<key>]`. The RU branch was translated to ES (Mexican coloquial) and stored as `UI_TEXTS["es"][<key>]`.
- **57 new keys** added to `UI_TEXTS` (ES + EN paralelas). Existing keys (`new_run`, `analysis_mode`, `versions_suffix`, `compare_summary`, `timeline_level`, `timeline_hint`) were reused.
- **Bug fixes piggy-backed:**
  - U1 mode toggle (`Deep` / `Глубокий`) fell to RU when `language=es`. Now uses `ui.mode_toggle_deep` / `ui.mode_toggle_simplified`.
  - `brain_region_panel` fallback dict literal used keys `title_ru` / `hint_ru` while the template lookup read `.title_es` / `.hint_es` — the fallback was effectively dead. Switched to `_es` keys with translated values.
  - Dead JS check at line 2500 used `.includes("Р")` (Cyrillic R) to detect RU tooltip labels. Simplified to a direct fallback.
  - Mojibake `В·` → `·` on the report-id chip.

---

## Pre-flight (run locally on Windows)

```powershell
cd F:\Github-Projects\tribe
git checkout refactor/s3-frontend-es
git pull
# 1. Cyrillic detector — must be 0 in template
python -c "import re; print(sum(len(m) for m in re.findall(r'[Ѐ-ӿ]+', open('templates/index.html', encoding='utf-8').read())))"
# 2. Jinja parse sanity
python -c "from jinja2 import Environment, FileSystemLoader, StrictUndefined; from report_localization import get_ui_texts; env = Environment(loader=FileSystemLoader('templates'), undefined=StrictUndefined); tpl = env.get_template('index.html'); print('[es]', len(tpl.render(language='es', ui=get_ui_texts('es'), title='x', result=None, error=None, page_base_url='/', pdf_mode=False))); print('[en]', len(tpl.render(language='en', ui=get_ui_texts('en'), title='x', result=None, error=None, page_base_url='/', pdf_mode=False)))"
# 3. Tests
python -m pytest -m "not slow" -q
```

Expected:
- Cyrillic counter prints `0`.
- Jinja render prints two `[lang] <N>` lines; no `UndefinedError`.
- pytest: `56 passed` (or `54 passed, 2 skipped` if ruff/torch absent).

---

## Visual smoke — main page (no result)

1. Launch the app:
   ```powershell
   cd F:\Github-Projects\tribe
   python -m uvicorn app:app --reload
   ```
2. Open `http://localhost:8000` — default ES.

   Check:
   - [ ] Hero card titles read **"Lee la curva"**, **"Entiende el frame"**, **"Acciona sobre el cut"**. No Cyrillic anywhere.
   - [ ] Upload section: button label **"Corrida nueva"**, chips read **"1 video = review a profundidad"** / **"2–4 videos = comparativa"** / **"se procesan uno por uno"**, helper text **"Sube un video para un review completo or de 2 a 4 videos para comparar versiones..."**.
   - [ ] Mode toggle: **"A profundidad"** / **"Simplificado"** (NOT "Глубокий" / "Упрощённый").
   - [ ] No `{{ }}` literals anywhere on the page — every Jinja expression resolved.

3. Open `http://localhost:8000?lang=en`.

   Check:
   - [ ] Hero cards in English: **"Read the curve"**, **"Understand the frame"**, **"Act on the cut"**.
   - [ ] Mode toggle: **"Deep"** / **"Simplified"**.
   - [ ] No ES bleed-through on text the user sees directly.

---

## Visual smoke — running state

1. Trigger an upload of a small video (`nanogel_tiktokv03.mp4` or similar). Default ES.
2. While analysis runs, the progress overlay should show:
   - [ ] **"Analizando"** as the heading.
   - [ ] **"Corriendo análisis TRIBE..."** as the live status.
   - [ ] **"Esto puede tardar"** as the wait note.
   - [ ] **"Los archivos pesados van uno por uno para que la app no se atore."** as the explanation.

---

## Visual smoke — result page

After analysis completes (deep mode, single video, ES):

- [ ] Report chip reads `Report <id> · <date>` (single middle dot, no `В·`).
- [ ] Mode pill reads **"Un solo cut"** (deep) or **"Modo comparativa"** (compare).
- [ ] Tab labels: **"Resumen"**, **"Qué hacer"**, **"Detalles"**, **"Zona de trabajo"** (not "Workspace" / "Сводка" / etc.).
- [ ] Disclaimer paragraph reads naturally in ES; `está` (not `es`); `video` (not `vídeo`).
- [ ] Prediction-details block: **"Duración"**, **"segundos"**, **"Tamaño del video"**, **"frames por segundo"**, **"Partes en el análisis"**, **"Momento más fuerte en la curva"**.
- [ ] Sources block: **"Fuentes oficiales del modelo"** + 2 link titles ES.
- [ ] Brain panel (if enabled): heading **"Zonas del cerebro en el análisis del video"**, hint **"Se muestran todas las zonas grandes..."**.

Now switch to EN (`?lang=en` or the language picker if exposed):
- [ ] Same page reads cleanly in English with no leftover ES.

---

## JS-side smoke (DevTools console)

With the result page open, in browser DevTools:

```js
// All four should print English (when lang=en) or Spanish (when lang=es), never Russian.
document.querySelectorAll(".chip, .pill, h3, .muted").forEach((n) => {
  if (/[Ѐ-ӿ]/.test(n.textContent)) console.warn("RU leak:", n.textContent);
});
console.log("done — no warnings = pass");
```

- [ ] Console prints `done — no warnings = pass`.

---

## Decision gate

| Check | Pass criterion |
|---|---|
| Cyrillic in `templates/index.html` | exactly `0` |
| Jinja `StrictUndefined` render | both `es` and `en` succeed |
| pytest `-m "not slow"` | all pass |
| Hero / upload / progress / result visual checks | every checkbox above ticked |
| `lang=en` visual check | no ES leak in user-facing text |
| Brain panel fallback (no DB region_panel) | shows ES title + hint, NOT empty |

If every row passes → mark PR ready and merge into main. If any visual check fails, file a follow-up describing which `ui.<key>` is wrong and the exact wording the user sees.

---

## Known out-of-scope leaks (NOT bugs for S3)

These are intentional residue from the post-hoc `localize_report` pipeline, slated for S5:

- 465 RU chars in `report_localization.py` — defensive matchers in `_normalize_focus_window_label` and `_rewrite_english_report` that scrub LLM output / legacy report payloads. Not user-visible while the engine is ES-only.
- 2 `if language == "en"` ternaries remain in `templates/index.html` (lines 2089–2090) reading `brain_region_panel.title_es` / `.hint_es` — these are DB-backed strings already provided in ES + EN by the engine. They stay as ternaries because they read attributes, not literal strings.

Treat any other ES↔EN mismatch as an S3 bug.
