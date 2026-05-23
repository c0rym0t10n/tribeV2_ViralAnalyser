# Stage 3 / S2 — manual smoke test (Ollama path → ES)

S2 is the half of Stage 3 that the engine snapshot suite cannot reach: it
touches the Ollama-rewrite path (LLM-driven simplified-mode copy) and the
strict-fallback that runs when Ollama is unreachable. Both paths now produce
Spanish, but goldens don't exercise either one — so the user-side gate is
**load-bearing** here.

## Procedure

```pwsh
Set-Location F:\Github-Projects\tribe
git checkout refactor/s2-ollama-es
```

### 1. With Ollama daemon up (LLM-rewrite path)

Make sure Ollama is running locally and at least one model in
`PREFERRED_MODELS` is loaded (the suggestion in the original plan was
`qwen2.5:14b`):

```pwsh
ollama list   # should include one of qwen3.5:9b / qwen35-27b-q4km / qwen35-27b-q3km / qwen2.5:14b
```

Run a simplified-mode review:

```pwsh
.\.venv\Scripts\python.exe smoke_test.py `
    --video path\to\nanogel_tiktokv03.mp4 `
    --output runtime_media\s2_simplified_es_ollama.json `
    --mode simplified `
    --language es
```

(Adapt flags to your local entrypoint — the important bits are
`mode=simplified` and `language=es`.)

### 2. With Ollama daemon down (strict-fallback path)

Stop Ollama (`ollama stop` or kill the process), then run the same review:

```pwsh
.\.venv\Scripts\python.exe smoke_test.py `
    --video path\to\nanogel_tiktokv03.mp4 `
    --output runtime_media\s2_simplified_es_fallback.json `
    --mode simplified `
    --language es
```

### 3. EN parity check

With Ollama up, run with `language=en`:

```pwsh
.\.venv\Scripts\python.exe smoke_test.py `
    --video path\to\nanogel_tiktokv03.mp4 `
    --output runtime_media\s2_simplified_en_ollama.json `
    --mode simplified `
    --language en
```

The LLM is prompted in EN-only when the prompt's "Spanish" instruction is
overridden — actually, post-S2 the prompt is hardcoded to ES. So
`language=en` will still produce ES from the LLM, then the post-hoc
`localize_report(report, "en")` pipeline translates to EN. That's the
documented behaviour for now (S5 owns retiring the post-hoc pipeline).

## Decision gate

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
" runtime_media\s2_simplified_es_ollama.json `
   runtime_media\s2_simplified_es_fallback.json `
   runtime_media\s2_simplified_en_ollama.json
```

| File | Expected | If not |
|---|---|---|
| `s2_simplified_es_ollama.json` | clean | LLM still emitted Russian despite the ES prompt — likely the model is too small to follow tone instructions reliably. Try a larger model or harden the prompt. |
| `s2_simplified_es_fallback.json` | clean | The strict-fallback library missed a string. Search ollama_concrete.py for the leaked substring. |
| `s2_simplified_en_ollama.json` | not clean (has ES) is OK | `language=en` post-S2 still goes through the `localize_report` post-hoc translator; full EN coverage moves in S5. |

## Tone review (subjective, but explicit)

Open `s2_simplified_es_ollama.json` and read these fields out loud:

- `verdict`, `executive_summary`, `product_summary`
- `strengths` (3), `weaknesses` (2-3)
- `recommendation_plan` (3 entries with title + detail)
- `action_items` (4-6 with title + instruction)
- `focus_windows[*].label`, `focus_windows[*].summary`

Confirm:

- [ ] No frase suena traducida con Google Translate.
- [ ] Action items en imperativo singular, sin "hay que" / "deberías".
- [ ] EN-preservados intactos: hook, cut, shot, frame, beat, payoff, caption, B-roll.
- [ ] "está" no "es" para calidad de edición.
- [ ] `copy_rewrite.provider == "ollama"` (otherwise the LLM call failed and we got the strict-fallback even though Ollama was up — flag in PR if so).
- [ ] Simplified-mode metric labels en EN jargon: `Hook` / `Retention` / `Pacing` / `Visual clarity` / `Visual punch`.

## What this smoke does NOT cover

- The frontend (`templates/index.html`). UI strings move in **S3**.
- Error messages from app.py — those are S1's surface (already done) but
  always worth a sanity check by triggering a missing-Chrome or
  missing-Whisper failure path on purpose.
- The ACTION_VARIANTS variety cap. Two videos with the same weak metrics
  produce identical action-item titles. Out of the language stack — own PR.

## Sign-off

Once both the Cyrillic gate (paths 1 + 2) and the tone review pass, mark
the PR ready for review. If anything reads off, paste the offending field
+ your alternate phrasing in the PR thread.
