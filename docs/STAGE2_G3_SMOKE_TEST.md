# Stage 2 / G3 — manual smoke test

Synthetic snapshot tests in `tests/test_golden_snapshots.py` cover band-shape
correctness with fabricated data. They are necessary but not sufficient: G3
shipped real changes to live code paths, so before merging the PR the engine
output should be exercised against a real video and compared to a pre-G3
baseline. This doc is the checklist for that.

## Why this matters

G3 lifted ten conditional-copy helpers out of `tribe_review.copy_ru` and into
`report_localization.METRIC_SUMMARY_LIBRARY_*` / `SPEECH_SUMMARY_LIBRARY_*`,
plus dropped five dead `_*_summary` ternaries from `generate_review`'s
`specs` list. The synthetic snapshot tests prove that the same `(metric_key,
score)` pair still maps to the same RU string. They do not prove that the
real-pipeline numbers (raw activations from TRIBE, Whisper word probabilities,
moviepy duration extraction) land in the same bands they did before.

If the RU JSON diverges from the pre-G3 baseline on a real run, the PR should
be reverted, not merged.

## Prereqs (one-time)

- Windows machine with the existing `.venv` (already has torch, tribev2,
  whisper, moviepy, ffmpeg).
- TRIBE checkpoint cached locally (the bootstrap will redownload if missing).
- A test video. The plan calls for `nanogel_tiktokv03.mp4`; any short video
  the user has run successfully on `main` works.

## Procedure

1. **Capture a pre-G3 baseline.**

   ```pwsh
   Set-Location F:\Github-Projects\tribe
   git checkout main          # before G3 lands
   .\.venv\Scripts\python.exe smoke_test.py --video path\to\nanogel_tiktokv03.mp4 --output runtime_media\baseline_pre_g3.json
   ```

   `smoke_test.py` is the existing local pipeline runner. If it doesn't take
   those exact flags, run the same workflow you normally use to produce a
   single-variant review JSON; the important bits are that it goes through
   `generate_review` end-to-end and dumps the resulting dict to disk.

2. **Run the same video through the G3 branch.**

   ```pwsh
   git checkout refactor/g3-conditional-copy
   .\.venv\Scripts\python.exe smoke_test.py --video path\to\nanogel_tiktokv03.mp4 --output runtime_media\g3_ru.json
   ```

3. **Compare.** The expected diff is the empty set. Use whatever diff tool
   you have:

   ```pwsh
   .\.venv\Scripts\python.exe -c "import json,sys; a=json.load(open(sys.argv[1],encoding='utf-8')); b=json.load(open(sys.argv[2],encoding='utf-8')); from deepdiff import DeepDiff; print(DeepDiff(a,b,ignore_order=False))" runtime_media\baseline_pre_g3.json runtime_media\g3_ru.json
   ```

   If `deepdiff` isn't installed, a plain `Compare-Object` on a `Get-Content
   -Raw` of each file is sufficient — they should be byte-identical for the
   parts the engine controls. The few fields that legitimately drift
   per-run (`report_id`, `created_at` — added at the API layer in `app.py`,
   not by the engine) are out of scope for this comparison; if you're
   comparing the raw `generate_review` output (no app.py wrapping), there
   are no volatile fields.

4. **EN smoke (optional but recommended).** Run with `language="en"`:

   ```pwsh
   .\.venv\Scripts\python.exe -c "
   import json, smoke_test  # adapt to your local entrypoint
   review = smoke_test.run('path/to/nanogel_tiktokv03.mp4', language='en')
   open('runtime_media/g3_en.json','w',encoding='utf-8').write(json.dumps(review, ensure_ascii=False, indent=2))
   "
   ```

   Open the EN output and confirm the five `metrics[*].summary` fields and
   the five `speech.metrics[*].summary` fields are in English. The rest of
   the report stays Russian — that's expected (see the G3-B commit message
   for the full scope note).

## Decision gate

| Result | Action |
|---|---|
| RU diff is empty | G3 is safe to merge. |
| RU diff is non-empty | Revert the G3 PR. The synthetic fixtures missed something the real pipeline exposes; the migration script in the PR description is idempotent so reverting and re-running with a tightened test fixture is straightforward. |
| EN output has empty `summary` fields | A `metric_key` doesn't have an entry in `METRIC_SUMMARY_LIBRARY_EN` or `SPEECH_SUMMARY_LIBRARY_EN` — fix the table in `report_localization.py`. Not a structural regression. |
| EN output has Russian inside the banded `summary` fields | Language threading didn't reach that call site. Check that `metric_band_summary` / `speech_metric_summary` are being called with `language=language`, not the default `"ru"`. |

## What this smoke does NOT cover

- The post-hoc `localize_report(report, "en")` pipeline. That path was untouched
  by G3 and continues to translate the still-Russian prose at the report
  layer. If you want to verify both paths together: run G3-EN on the engine,
  then run `localize_report` on top, and confirm the result is fully English.
- The PDF / web rendering layer. G3's surface is the engine JSON; rendering
  has its own translation hooks unrelated to `generate_review`.
