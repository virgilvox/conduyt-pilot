# 2026-04-28 v3 corpus: Arduino vs conduyt-js disambiguation

## Why

v1 / v2 model output mashed Arduino C++ idioms into JavaScript:

- `device.arduino.createServo(18)` (hallucinated namespace)
- `millis()`, `delay()`, `map()` used as JS globals
- `device.pinMode(13, OUTPUT)` (Arduino-style on the JS device proxy)

Diagnosis: v1 had 12 percent conduyt-js coverage and zero contrastive signal;
v2 added 92+ conduyt-js examples but still no examples that distinguished
Arduino C++ from conduyt-js JavaScript explicitly. The model had two strong
priors from pretraining and no supervision on the boundary.

The fix is contrastive learning, not more volume.

## What changed

Six new seed files in `data/seeds/`:

| File | Count | Purpose |
|------|-------|---------|
| `v3_arduino_reference.jsonl` | 20 | Pure Arduino C++ sketches, anchored Arduino-only system prompt |
| `v3_conduyt_js_mirror.jsonl` | 20 | Mirrors of the same tasks in conduyt-js, anchored "no Arduino primitives" system prompt |
| `v3_side_by_side.jsonl` | 15 | Single response, Arduino sketch + conduyt-js host code, clearly labeled |
| `v3_disambiguation.jsonl` | 20 | "Is this Arduino or conduyt-js?" / "Spot the bug" classifiers |
| `v3_dont_mix.jsonl` | 15 | System prompt forbids Arduino primitives in JS; user asks JS task; assistant produces clean JS |
| `v3_multiturn_evolve.jsonl` | 6 | Multiturn conversations (3 turns each) staying in conduyt-js without sliding into Arduino |

Total new: 96 examples. Plus the 25 in the existing `v3_conduyt_docs.jsonl`
from a prior session.

## System prompts

Five distinct system prompts now anchor different bucket roles:

1. `SYS_ARDUINO`: "Output Arduino sketch only. Do not output JavaScript..."
2. `SYS_CONDUYT_JS`: "Output JavaScript or TypeScript only. Do not use
   Arduino primitives like digitalWrite() or millis() in JavaScript code."
3. `SYS_BOTH`: "When asked to show both, output two separate, clearly
   labeled code blocks. Never mix Arduino primitives into the JavaScript
   block."
4. `SYS_DISAMBIG`: "Strict code classifier and debugger for two toolchains."
5. `SYS_DONT_MIX`: "JavaScript does not have digitalWrite, pinMode, millis,
   delay, or Arduino-style map. Those are Arduino C++ primitives."

The prompts themselves are training signal. They explicitly name which
toolchain the response should belong to and what is out of bounds.

## Validation

```
python3 scripts/02_validate_dataset.py data/seeds/v3_*.jsonl
v3_arduino_reference.jsonl: total=20 kept=20 dropped=0
v3_conduyt_js_mirror.jsonl: total=20 kept=20 dropped=0
v3_side_by_side.jsonl:      total=15 kept=15 dropped=0
v3_disambiguation.jsonl:    total=20 kept=20 dropped=0
v3_dont_mix.jsonl:          total=15 kept=15 dropped=0
v3_multiturn_evolve.jsonl:  total=6  kept=6  dropped=0
total kept: 96, dropped: 0
```

Cross-file dedup: 1 exact duplicate dropped (out of 365 across all v1/v2/v3
clean + the synthetic batch).

## Final split

```
train: 329 examples
eval:  35 examples
total: 364

stratification by board:
  adafruit-feather-esp32-s3:        15
  adafruit-feather-nrf52840-sense:  13
  arduino-nano-33-ble:              10
  arduino-uno-r4-wifi:              80
  esp32-s3-devkitc-1:              121
  raspberry-pi-pico:                60
  raspberry-pi-pico-w:               9
  seeed-xiao-esp32-c3:              11
  (untagged: ~45, mostly disambig classifiers)
```

## Hallucination check

Grepped final train.jsonl + eval.jsonl for `device.arduino.<x>`. Two hits:
both in `dont-mix` (line 20) and `disambiguation` (line 187) buckets. Those
are negative examples by design (the assistant flags them as wrong and
gives the correct fix). No hallucination patterns leak into positive
training signal.

## Bundle

`conduyt-pilot-data-v3.zip` (135 KB):

```
metadata.json
train.jsonl  (329)
eval.jsonl   (35)
boards/      (8 JSONs)
```

## Open items / next session

- v3 bundle upload to Kaggle (manual or API-key-driven)
- v3 fine-tune run on Kaggle T4 x2 with `kaggle/train.ipynb` (existing
  hyperparameters: r=32, alpha=64, dropout=0, 5 epochs)
- MLC export with the existing `kaggle/convert_mlc.ipynb`
- WebLLM smoke test once MLC artifacts land

## End-to-end automation feasibility

The user asked whether the assistant can take their Kaggle + HF API keys
and run the whole pipeline. Yes, with these pre-flight items:

1. User drops `kaggle.json` at `~/.kaggle/kaggle.json` (chmod 600). Never
   committed; gitignored at the dotfile level.
2. User exports an HF write token (`huggingface-cli login` or env var
   `HF_TOKEN`). Never committed.
3. The assistant pushes the v3 dataset version, pushes the training
   kernel, monitors by polling `kaggle kernels status` every ~25 minutes
   (Kaggle session is 12hr max; full run is ~4-5 hrs).
4. On completion: `kaggle kernels output` to pull artifacts; then
   `huggingface-cli upload` to push GGUF + MLC artifacts to two HF repos
   (`virgilvox/conduyt-coder-1p5b` and `virgilvox/conduyt-coder-1p5b-MLC`).
5. End artifact: an HF MLC repo loadable by WebLLM via a custom
   `appConfig` snippet handed back to the user.

Risks the user should accept before pulling the trigger:

- One run burns ~4-5 hr of the 30 hr/week T4 quota; one retry is another
  ~4-5 hr.
- Quality is data-bound. The pipeline runs end-to-end and produces
  loadable artifacts; whether the model still mashes Arduino-into-JS is
  what eval prompts will tell us.
- Tokens are gitignored and never logged. Rotation stays user-side.
- Kaggle queue at peak hours (Pacific evening) can delay the start.
