# Stage 3 / S1 — manual smoke test (ES tone + RU absence)

The synthetic snapshot tests in `tests/test_golden_snapshots.py` cover band
shape and language threading on fabricated input. Before merging S1, run the
real pipeline against a real video and confirm:

1. **No Russian leaks anywhere in the JSON.** Every prose field must be ES
   (or, on the EN path, EN). If you find Cyrillic, S1 has missed a string.
2. **Tone reads naturally to a creator.** "De volada", "tumba", "amarra"
   should land like a video editor would actually say them — not like
   Google Translate.
3. **EN-preserved terms stay EN.** `hook`, `cut`, `shot`, `frame`, `beat`,
   `payoff`, `caption`, `B-roll`, `opening`, `CTA`, `retention`, `drop-off`
   should appear in English even inside ES sentences.
4. **Simplified mode shows EN jargon labels.** Metric names in simplified-
   mode reports are `Hook` / `Retention` / `Pacing` / `Visual clarity` /
   `Visual punch` — never Russian, never Spanish. (This was the user-flagged
   bug; S1-3b fixed it.)
5. **The Ollama rewrite path doesn't reintroduce Russian.** If the local
   Ollama server is running, simplified mode will call the LLM. Verify the
   `copy_rewrite.provider == "ollama"` path produces ES output, not RU.

## Procedure

```pwsh
Set-Location F:\Github-Projects\tribe
# Make sure you're on the S1 branch
git checkout refactor/s1-es-primary

# 1. Deep mode, ES default
.\.venv\Scripts\python.exe smoke_test.py `
    --video path\to\nanogel_tiktokv03.mp4 `
    --output runtime_media\s1_deep_es.json `
    --mode deep
# adapt the flags to whatever smoke_test.py exposes today; the important
# bits are language defaults to "es" and analysis_mode="deep".

# 2. Simplified mode, ES (this is the path the LLM rewrites)
.\.venv\Scripts\python.exe smoke_test.py `
    --video path\to\nanogel_tiktokv03.mp4 `
    --output runtime_media\s1_simplified_es.json `
    --mode simplified

# 3. EN path
.\.venv\Scripts\python.exe -c "
import json, smoke_test
review = smoke_test.run('path/to/nanogel_tiktokv03.mp4', language='en', mode='deep')
open('runtime_media/s1_deep_en.json','w',encoding='utf-8').write(json.dumps(review, ensure_ascii=False, indent=2))
"
```

## Decision gate

Run this Cyrillic-leak detector against every output JSON:

```pwsh
.\.venv\Scripts\python.exe -c "
import json, re, sys
for path in sys.argv[1:]:
    text = open(path, encoding='utf-8').read()
    matches = re.findall(r'[Ѐ-ӿ]+', text)
    if matches:
        unique = sorted(set(matches))[:10]
        print(f'{path}: {len(matches)} Cyrillic runs, sample: {unique}')
    else:
        print(f'{path}: clean')
" runtime_media\s1_deep_es.json runtime_media\s1_simplified_es.json runtime_media\s1_deep_en.json
```

| Result | Action |
|---|---|
| All three files print `clean` | Cyrillic gate passes. Move to tone review. |
| Any file shows Cyrillic runs | S1 has missed a string. Identify which module emits it (search the repo for the exact phrase) and either patch S1 directly or document as a known leak in the PR description before merging. **Do not merge with leaks.** |

## Tone review (subjective, but explicit checklist)

Open `s1_deep_es.json` and read the following fields out loud:

- `verdict`
- `executive_summary`
- `product_summary`
- `strengths` (3 entries)
- `weaknesses` (2-3 entries)
- `recommendations` (top 6)
- `recommendation_plan` (3 entries with title + detail)
- `action_items` (4-6 entries with title + instruction)
- `focus_windows[*].label`, `focus_windows[*].summary`

Yes / no for each:

- [ ] No frase suena traducida con Google Translate. Cada oración suena como un editor de video mexicano la diría.
- [ ] "De volada" no sobre-aparece (debería caer 1-2 veces como mucho en un reporte completo).
- [ ] Action items en imperativo singular, sin "hay que" ni "deberías".
- [ ] Hooks / cuts / frames / beats están en EN, no traducidos a "ganchos" / "cortes" / "encuadres" / "tiempos".
- [ ] Verbos de estado: "está flojo", "está fuerte", "se cae" — nunca "es flojo", "es fuerte".

## Simplified mode + Ollama rewrite gate

If your local Ollama server is up with one of `PREFERRED_MODELS`:

- Open `s1_simplified_es.json`.
- Confirm `copy_rewrite.provider == "ollama"` (otherwise the fallback was used and we need to review the LLM prompt path in S2).
- Verify all metric labels are EN jargon (`Hook` / `Retention` / `Pacing` / `Visual clarity` / `Visual punch`).
- Verify `signal_note`, `weaknesses[*]`, `action_items[*].title` and `*.instruction` all read in ES.

## What this smoke does NOT cover

- The frontend (`templates/index.html`). UI strings come from `UI_TEXTS`
  via the i18n layer — S1-2 added the ES dict, but the templates themselves
  still hold Russian strings. **S3** owns the frontend flip.
- The `localize_report(report, "en")` post-hoc EN translation. The
  `LABEL_MAP_EN` population block was retrained to ES-keyed in S1-3a, but
  several of the `_rewrite_*_en` helpers still scan for RU substrings. The
  engine no longer emits those substrings, so in practice the EN path
  works, but a full audit lives in **S5**.
- Error messages emitted by `app.py`'s `_format_error`. **S4** owns those.

## Sign-off

Once the Cyrillic gate is clean and the tone review reads naturally, mark
the PR ready for code review. If anything reads off, paste the offending
field + your alternate phrasing in the PR thread — quick fix in a follow-up
commit before merge.
