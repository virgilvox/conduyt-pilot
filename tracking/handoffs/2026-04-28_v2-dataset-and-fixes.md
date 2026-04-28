# Handoff: 2026-04-28 — v2 dataset + Kaggle fixes

Closes the loop on every issue surfaced during the v1 Kaggle run.

## What ran end-to-end on v1

The v1 pipeline shipped: Kaggle dataset upload -> Unsloth QLoRA fine-tune on T4 x2 -> GGUF push -> MLC conversion -> `@mlc-ai/web-llm` browser inference. The model loads in the browser and responds. **The infrastructure works.**

## What the v1 fine-tune got wrong

Eyeball test of the running model showed structural code errors. From the user's chat log:

```js
// MODEL OUTPUT (wrong):
const device = await ConduytDevice.connect()              // missing transport
const servo = await device.arduino.createServo(18)         // hallucinated namespace
const led = device.arduino.pin(13, 'output')               // hallucinated namespace
const pos = map(pot.read(), 0, 1023, 0, 180)               // Arduino C++ globals in JS
await delay(20)                                            // Arduino-ism
```

Diagnosis: only ~12% of v1 training was conduyt-js, all single-turn. Base Qwen2.5-Coder-1.5B has a strong Arduino prior; r=16 over 3 epochs couldn't override it. v1 also had API drift from the README — some examples used `subscribe({ mode: 'analog' })` (string mode) when the actual API takes a numeric `SUB_MODE` constant.

## v2 fixes

### Dataset additions (93 new examples, 243 total)

All v2 examples were verified line-by-line against `../conduyt/sdk/js/src/` (device.ts, modules/*.ts, transports/*.ts, core/types.ts, core/constants.ts, core/errors.ts, ota.ts, reconnect.ts).

| File | Count | Purpose |
|---|---|---|
| `data/raw/v2_single_turn.jsonl` | 30 | Cover every transport (Serial, WebSerial, BLE, MQTT, WebSocket, Mock, ReconnectTransport), every module (Servo, NeoPixel, OLED, DHT, Encoder, Stepper, PID), every error class, async iteration patterns, datastreams, I2C bridge, capability inspection, OTA. |
| `data/raw/v2_multi_turn.jsonl` | 32 | 5-message conversations (system + user1 + asst1 + user2 + asst2). Turn 2 builds on turn 1 without restating imports/connection. Includes the EXACT failure mode the user observed (servo + LED blink + pot follow). |
| `data/raw/v2_arduino_override.jsonl` | 20 | User uses Arduino C++ vocabulary (`digitalWrite`, `analogRead`, `millis`, `delay`, `Wire.begin`, `Servo myServo`, `Serial.print`, etc.); assistant responds with the conduyt-js API anyway. Direct inoculation. |
| `data/raw/v2_api_docs.jsonl` | 10 | Q&A reference style: import paths, method signatures, error class differences, capability shape, top-level exports. Anchors the model on the actual API surface. |

### Validator update
`scripts/02_validate_dataset.py` now accepts both 3-message single-turn and 5+-message multi-turn examples, with role-alternation checks. Code-fence balance check runs on all assistant messages, not just the third.

### Hyperparameter changes (train.ipynb)
- `r=16 -> 32`
- `lora_alpha=32 -> 64`
- `lora_dropout=0.05 -> 0` (engages Unsloth fast-patching kernels)
- `num_train_epochs=3 -> 5`

### Pipeline fixes baked into the notebooks
- **`huggingface_hub` unpinned**: v1's `==1.12.0` collided with `transformers==4.56.2`'s `<1.0` cap. Now lets pip resolve.
- **Auto-discover dataset path**: `glob /kaggle/input/**/train.jsonl` handles both legacy `/kaggle/input/<slug>/` and current `/kaggle/input/datasets/<user>/<slug>/` layouts.
- **MLC CPU wheels**: `mlc-{llm,ai}-nightly-cpu` instead of cu128/cu122. cu128 had TVM `tirx` regression + `libcudart.so.12` link issue at import time.
- **`python -m mlc_llm`**: bypass Kaggle's PATH not picking up pip entry-point scripts.
- **`--device cpu` for `convert_weight`**: skips the GPU codegen path.
- **Bridge cell**: train.ipynb auto-pushes `/kaggle/working/merged` to `virgilvox/conduyt-pilot-1.5b-v2-merged` so convert_mlc.ipynb (fresh kernel) can `snapshot_download` it.

### Repo names
All Phase 2 artifacts shift to `-v2-` suffix to keep v1 and v2 side-by-side:
- `virgilvox/conduyt-pilot-1.5b-v2-lora`
- `virgilvox/conduyt-pilot-1.5b-v2-merged`
- `virgilvox/conduyt-pilot-1.5b-v2-gguf`
- `virgilvox/conduyt-pilot-1.5b-v2-MLC`

## Final v2 corpus

```
total            : 243 examples (was 151 in v1)
single-turn      : 211
multi-turn       : 32

by board:
  esp32-s3-devkitc-1               : 113
  raspberry-pi-pico                :  57
  arduino-uno-r4-wifi              :  20
  adafruit-feather-esp32-s3        :  15
  adafruit-feather-nrf52840-sense  :  11
  seeed-xiao-esp32-c3              :  11
  raspberry-pi-pico-w              :   9
  arduino-nano-33-ble              :   7

by kind:
  v1-or-seed                       : 151
  conduyt-js (v2 single)           :  30
  conduyt-js-multiturn (v2)        :  32
  conduyt-js-arduino-override (v2) :  20
  conduyt-js-docs (v2)             :  10

train/eval split: 220 train + 23 eval (90/10 stratified by board_id)
bundle: conduyt-pilot-data-v2.zip (~290 KB, 11 files)
validation: 0 violations on the full 243-example corpus
```

## Persistent memories saved

- `identities.md`: Kaggle is `moheebzara`; HF + GitHub are `virgilvox`. Don't conflate.
- `kaggle_dataset_mount_path.md`: `/kaggle/input/datasets/<user>/<slug>/` in 2026, not legacy.
- `kaggle_path_quirk.md`: pip entry-point scripts aren't on PATH; use `python -m <pkg>`.

## What to do next

1. Upload `conduyt-pilot-data-v2.zip` to Kaggle as a new version of the existing `conduyt-pilot-data` dataset.
2. Run `kaggle/train.ipynb` (the bumped pinning + v2 hyperparameters). ~45-75 min on T4 x2.
3. Run `kaggle/convert_mlc.ipynb` (CPU wheels). ~10-15 min.
4. Eyeball test: `uv run scripts/06_test_local.py --finetune-repo virgilvox/conduyt-pilot-1.5b-v2-gguf`. Compare base vs finetune on 5 probes + 10 random eval prompts.
5. If the model now produces correct conduyt-js (`new ConduytServo(device); await servo.attach(N)` instead of `device.arduino.createServo(N)`), v2 works; ship it.
6. If it still hallucinates, the next levers are: more conduyt-js examples (push to ~150 total), bigger base model (Qwen2.5-Coder-3B fits T4 in 4-bit), or higher r=64.

## Open questions

- Did the v2 multi-turn examples solve the follow-up-conversation drift? Will know after Step 4 above.
- Should the synthesis script (`scripts/01_generate_synthetic.py`) be retired in favor of always using Claude-as-synthesizer in-conversation? Probably yes — v1 + v2 corpus were both written that way and it's both cheaper and lower-friction. Keep the script for fully-autonomous batch jobs but the README's main path should be in-conversation.
