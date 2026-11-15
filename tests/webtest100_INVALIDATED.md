# webtest100 INVALIDATED as a held-out test (2026-11-15)

## Project-owner decision
All 102 webtest100 images were burned into round-5 fine-tune training
(`ai_engine/finetune_v7_webtest.py`, manifest `ai_engine/ROUND5_FINETUNE_MANIFEST.json`,
version `5.0-round5-webtest-burned`).

## Consequences
- **Any score of any model on webtest100 from this date is memorization, not
  generalization.** Do not quote webtest100 numbers for round-5+ models.
- Historical numbers below remain valid ONLY for models trained BEFORE this
  decision (sha-prefix, webtest100 raw argmax):
  - round-3 v4 (`ba9f334a`): 44/102
  - round-4 v7 raw (`b0c6c39a`): 56/102 — this was the round-4 headline
  - round-4 fine-tune artifacts (rejected): v1 `6fbe53c3` 43/102, v2b `ed6974e2` 52/102

## Replacement held-out web test
A fresh 100-image set will be harvested with the same protocol (query-driven
Bing/Edge collection, operator-verified labels, sha256+dHash dedupe against
everything ever trained on) AFTER the round-5 model is finalized. Until that
set exists, the honest held-out web-domain number for round-5 models is
**unmeasured** — say so plainly rather than quoting webtest100.

## What remains held-out and honest
- benchmark-60 specimens (`ai_engine/validation_60_specimens/`) — per-epoch
  guard in the round-5 fine-tune; never trained on
- PlantVillage valid split — never trained on
- chart/palm OOD set — never trained on
