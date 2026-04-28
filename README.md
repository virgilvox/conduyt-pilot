# conduyt-pilot

Fine-tune toolkit for a small embedded-coding model. Phase 1 builds a clean training dataset of (system, user, assistant) chat triples covering 8 representative MCU boards across Arduino, PlatformIO, ESP-IDF, Conduyt firmware, and conduyt-js. Phase 2 runs an Unsloth + QLoRA fine-tune of `Qwen2.5-Coder-1.5B-Instruct` on Kaggle's free T4 tier, then exports GGUF (Ollama / llama.cpp / Pi) and MLC (browser via WebLLM).

**The current corpus** (`conduyt-pilot-data-v5.zip`, 502 examples, 215 KB):
- 151 hand-curated v1 seed + synthetic examples (Arduino, PlatformIO, ESP-IDF, NeoPixel, I2C, SPI, conduyt firmware, conduyt-js, ESP32 WiFi)
- 92 v2 conduyt-js batches: 30 single-turn (every transport / module / error class), 32 multi-turn conversations, 20 Arduino-vocab override examples, 10 API doc-style Q&A
- 25 doc-derived examples extracted from `../conduyt/site/content/docs/` via `scripts/07_extract_conduyt_docs.py`
- **96 v3 contrast examples**: Arduino-only and conduyt-js-only buckets, side-by-side anchor pairs, disambiguation classifiers, dont-mix hardening, multi-turn evolutions. Teaches the model the boundary between Arduino C++ and conduyt-js JavaScript.
- **115 v4 hardware/electronics breadth examples**: Ohm's-law math, component selection with part numbers, circuit recipes (MOSFET switching, level shifting, INA219), protocol pitfalls, sensor wiring + code, actuator drive, power management, ranked debug walkthroughs, end-to-end project archetypes, per-board hardware facts.
- **23 v5 mascarade imports** (MIT, electron-rare/mascarade): bare-metal ARM Cortex-M4 + RISC-V + Raspberry Pi + Teensy startup, STM32F4 LL drivers, ESP-IDF MQTT + TLS, FreeRTOS architecture, ESPAsyncWebServer, custom PlatformIO board.json, BLDC FOC with Clarke/Park transforms, half-bridge gate driver thermal calc.

See `THIRD_PARTY.md` for upstream attribution. See `tracking/handoffs/` for per-version rationale.

## Setup

```bash
# Python 3.11 required.
uv sync

# Optional: enable semantic dedup
uv sync --extra semantic
```

## Where things are

```
data/seeds/                  hand-curated + doc-derived examples (committed)
data/boards/                 8 board capability profiles (committed)
data/raw/                    synthetic outputs (gitignored)
data/processed/              cleaned/validated/split outputs (gitignored)
prompts/                     synthesis system + template prompts
scripts/                     pipeline (01-05) + local GGUF test (06) + docs extractor (07)
kaggle/                      train.ipynb + convert_mlc.ipynb + troubleshooting
tracking/handoffs/           session handoffs
THIRD_PARTY.md               upstream attribution for imported content
conduyt-pilot-data-v5.zip    the current Kaggle bundle (gitignored)
```

---

# Run the fine-tune (the part you do yourself in Kaggle)

The repo ships with `conduyt-pilot-data-v5.zip` already built (215 KB, 502 examples).

## What's in the zip

```
metadata.json                               # dataset info: counts, schema, version
train.jsonl                                 # 453 chat-format examples
eval.jsonl                                  #  49 chat-format examples
boards/adafruit-feather-esp32-s3.json
boards/adafruit-feather-nrf52840-sense.json
boards/arduino-nano-33-ble.json
boards/arduino-uno-r4-wifi.json
boards/esp32-s3-devkitc-1.json
boards/raspberry-pi-pico-w.json
boards/raspberry-pi-pico.json
boards/seeed-xiao-esp32-c3.json
```

Verify it's there:

```bash
ls -lh conduyt-pilot-data-v5.zip
unzip -l conduyt-pilot-data-v5.zip
```

## Step 1: get a Hugging Face write token

1. https://huggingface.co/settings/tokens -> New token
2. Type: **Write**
3. Name it something like `conduyt-pilot-kaggle`
4. Copy the `hf_...` string. You'll paste it into Kaggle Secrets in step 3.

The notebooks push to four HF repos under `virgilvox/` on first run (they use `create_repo(exist_ok=True)`):
- `virgilvox/conduyt-pilot-1.5b-v5-lora` (LoRA adapter)
- `virgilvox/conduyt-pilot-1.5b-v5-merged` (merged 16-bit, used by the MLC step)
- `virgilvox/conduyt-pilot-1.5b-v5-gguf` (Q4_K_M, Q5_K_M, Q8_0)
- `virgilvox/conduyt-pilot-1.5b-v5-MLC` (q4f16_1 for WebLLM)

## Step 2: upload the dataset to Kaggle

If this is the first upload, **New Dataset**; if you're shipping an updated version, **Add a new version** to the existing slug.

1. https://www.kaggle.com/datasets -> **New Dataset** (first time) or open `moheebzara/conduyt-pilot-data` -> **New Version**
2. Drag `conduyt-pilot-data-v5.zip` into the upload area. Kaggle will unpack it.
3. **Title / slug:** `conduyt-pilot-data` (the slug must be `conduyt-pilot-data`; the version bumps automatically when you upload a new zip)
4. **Visibility:** Private
5. Create

**Heads-up about the mount path:** Kaggle in 2026 mounts attached datasets at `/kaggle/input/datasets/<your-kaggle-username>/<slug>/`. For this project that resolves to `/kaggle/input/datasets/moheebzara/conduyt-pilot-data/`. The train notebook auto-discovers either layout via `glob /kaggle/input/**/train.jsonl`, so you don't need to hardcode the path.

The Kaggle username (`moheebzara`) and HF username (`virgilvox`) are different. The dataset path uses the kaggle one; HF push targets use the HF one. Don't conflate.

## Step 3: create the train notebook on Kaggle

1. https://www.kaggle.com/code -> **New Notebook**
2. **File -> Import Notebook -> Upload** -> pick `kaggle/train.ipynb` from this repo
3. Right-side panel:
   - **Accelerator:** GPU T4 x1 (single T4). Stock Unsloth doesn't auto-shard a 1.5B QLoRA across two GPUs, so picking T4 x2 would burn 2x quota for the same speed. The 16 GB on a single T4 is plenty for QLoRA on a 1.5B model.
   - **Internet:** ON
   - **Persistence:** ON
4. **Add data** (right panel) -> search for `conduyt-pilot-data` -> Add. (Use the latest version.)
5. **Add-ons -> Secrets** (top menu):
   - Add `HF_TOKEN` with the value from step 1
   - Optional: `WANDB_API_KEY` for run logging
6. **Edit the HF repo names** if your HF user isn't `virgilvox`. Search the notebook for `virgilvox` and replace.

## Step 4: run train.ipynb

Click **Run All**. Expected wall time on T4 x1: roughly **60-90 minutes** for 453 examples x 5 epochs on the 1.5B base. Training itself is ~30-45 min; GGUF quantize is ~10-15 min; HF upload is ~10-15 min depending on network.

What happens, in order:
1. Pinned installs (`unsloth==2026.4.8`, `transformers==4.56.2`, `trl==0.22.2 --no-deps`, etc.). `huggingface_hub` is intentionally NOT pinned (transformers 4.56.2 caps it at `<1.0`; v1's pin to 1.12.0 broke the install).
2. Loads `HF_TOKEN` and (optionally) `WANDB_API_KEY` from Kaggle Secrets.
3. **Auto-discovers** the dataset path under `/kaggle/input/**/train.jsonl`.
4. Loads `unsloth/Qwen2.5-Coder-1.5B-Instruct` in 4-bit.
5. Applies LoRA: `r=32, lora_alpha=64, dropout=0` (unchanged across v2-v5). Bigger r gives more override capacity against the base model's Arduino prior. dropout=0 enables Unsloth's fast-patching kernels (~2-3x faster than dropout>0).
6. Formats with the Qwen2.5 chat template via `tokenizer.apply_chat_template`.
7. Trains with SFTTrainer: bs=2, grad-accum=4 (effective 8), **5 epochs**, 2e-4 LR, fp16 (T4-required).
8. Saves the LoRA adapter to `/kaggle/working/adapter` and pushes it to `virgilvox/conduyt-pilot-1.5b-v5-lora`.
9. Runs 5 sanity inference probes that each test a different bucket of the v5 corpus: dont-mix (v3), side-by-side (v3), hardware fundamentals (v4), debug walkthrough (v4), bare-metal ARM (v5 mascarade). Eyeball the output for voice + API correctness.
10. Merges LoRA into the base weights and saves at `/kaggle/working/merged`.
11. Exports GGUF at q4_k_m / q5_k_m / q8_0 and pushes the three files to `virgilvox/conduyt-pilot-1.5b-v5-gguf`.
12. **Auto-pushes the merged model** to `virgilvox/conduyt-pilot-1.5b-v5-merged`. This bridges to `convert_mlc.ipynb`, which runs in a fresh kernel that can't see `/kaggle/working/`.

When it finishes you'll have lora + gguf + merged on HF, ready for the MLC step.

## Step 5: run convert_mlc.ipynb

1. https://www.kaggle.com/code -> **New Notebook** -> Import `kaggle/convert_mlc.ipynb`
2. Accelerator: **GPU T4** (single is fine; we use CPU MLC wheels anyway)
3. Internet: ON, Persistence: ON
4. Add-ons -> Secrets -> `HF_TOKEN`
5. **Run All**. Wall time: ~15-25 minutes (most is the upload).

**Three known fixes baked in:**
- **CPU-only MLC wheels** (`mlc-{llm,ai}-nightly-cpu`) instead of cu* variants. The cu128 nightlies in 2026-04 had a TVM `tirx`/`s_tir` regression and a `libcudart.so.12` link issue at import time. CPU wheels have no CUDA dep and just work.
- **`python -m mlc_llm`** invocation instead of bare `mlc_llm`. Kaggle's PATH doesn't pick up pip entry-point scripts.
- **`--device cpu`** for `convert_weight`. The math is the same; this side-steps the CUDA codepath that was crashing.

This produces:
- `virgilvox/conduyt-pilot-1.5b-v5-MLC` on HF (weights + config for WebLLM)
- A printed `appConfig` snippet for `@mlc-ai/web-llm`. Drop it into your client-side bootstrap. The `model_lib` URL in that snippet points at `web-llm-models/v0_2_83/base/Qwen2-1.5B-Instruct-q4f16_1_cs1k-webgpu.wasm`, which was HTTP-200 verified at notebook authoring time.

## Step 6: smoke-test the GGUF locally

Back on your machine:

```bash
uv sync
uv run scripts/06_test_local.py --finetune-repo virgilvox/conduyt-pilot-1.5b-v5-gguf
```

This pulls the Q4_K_M GGUF from `virgilvox/conduyt-pilot-1.5b-v5-gguf` and the matching base GGUF from Qwen, runs 5 hardcoded probes plus 10 random prompts from `data/processed/eval.jsonl`, and writes a side-by-side comparison report to `tracking/notes/local_eval_results.md`.

If the fine-tuned column reads in your voice and uses the actual conduyt-js API (`device.pin().mode()`, `new ConduytServo(device); await servo.attach(N)`) while the base column reads like generic Arduino-flavored JS, the train worked.

Flags:

```bash
uv run scripts/06_test_local.py --quant Q5_K_M     # try a different quant
uv run scripts/06_test_local.py --skip-base        # only run finetune
uv run scripts/06_test_local.py --n-eval 25        # more eval probes
```

---

# What you can do with the artifacts

| HF repo | Use it for |
|---|---|
| `virgilvox/conduyt-pilot-1.5b-v5-gguf` | `ollama create conduyt -f Modelfile && ollama run conduyt`. Or `llama.cpp` directly. Or LM Studio. |
| `virgilvox/conduyt-pilot-1.5b-v5-MLC` | Browser inference with WebGPU via `@mlc-ai/web-llm`. |
| `virgilvox/conduyt-pilot-1.5b-v5-lora` | Low-storage distribution: anyone with the base model can apply this ~50 MB adapter. |
| `virgilvox/conduyt-pilot-1.5b-v5-merged` | Anywhere HF transformers / vLLM runs. |

---

# Regenerate the dataset (only if you've changed seeds or want more synthetic)

The pipeline is six scripts, each writing a typed output. Note: synthetic examples can be generated either by an in-conversation assistant (no API spend) or by running the script against an LLM API directly.

```bash
# 1. (optional) Generate more synthetic via the live API.
export ANTHROPIC_API_KEY=...
uv run scripts/01_generate_synthetic.py --dry-run                 # inspect first
uv run scripts/01_generate_synthetic.py --limit 300 --max-cost-usd 2.50

# 2. Validate everything (seeds + raw synthetic).
uv run scripts/02_validate_dataset.py data/seeds/*.jsonl data/raw/*.jsonl

# 3. Combine clean files, dedupe.
cat data/processed/*_clean.jsonl > data/processed/all.jsonl
uv run scripts/03_dedupe_dataset.py data/processed/all.jsonl --out data/processed/dedup.jsonl

# 4. 90/10 split, stratified by board_id.
uv run scripts/04_split_train_eval.py data/processed/dedup.jsonl

# 5. Bundle for Kaggle. Outputs conduyt-pilot-data-v<N>.zip in the repo root.
uv run scripts/05_build_kaggle_dataset.py
```

After regenerating, re-upload the new zip to Kaggle as a new version of the `conduyt-pilot-data` dataset.

The validator (script 02) accepts both single-turn (3 messages: system/user/assistant) and multi-turn (5+ messages with proper alternation). Multi-turn examples teach the model to maintain API consistency across follow-up prompts.

## Pulling more from the conduyt docs

`scripts/07_extract_conduyt_docs.py` walks `../conduyt/site/content/docs/`, strips YAML frontmatter, normalizes em/en dashes, scrubs banned phrases, and emits one training example per doc. Module docs have known API drift (e.g. `import { Servo }` instead of the actual `ConduytServo`), so the script strips code blocks from those by default and keeps only the prose (wiring tables, hardware notes, command reference). Concept and how-to docs ship with code intact.

```bash
uv run scripts/07_extract_conduyt_docs.py
# wrote 26 examples to data/raw/v3_conduyt_docs.jsonl
# 4 drift warnings (already neutralized by stripping code from those docs)

# After spot-checking, promote into seeds:
mv data/raw/v3_conduyt_docs.jsonl data/seeds/v3_conduyt_docs.jsonl
# Then rerun the regen pipeline above.
```

Re-run whenever the conduyt docs evolve. The extractor's drift-warning system flags any code block that uses a deprecated import or constructor pattern; if a new one slips in, add a regex to `DRIFT_PATTERNS` in the script.

---

# Trajectory across versions

The base hyperparameters were tuned in v2 and have been held fixed across v3, v4, v5 because the wins from those versions came from dataset growth, not training tweaks.

| Version | Train | Eval | Total | Bundle | What grew |
|---|---|---|---|---|---|
| v1 | 90 | 0 | 90 | 48 KB | Initial seeds + synthesis |
| v2 | 243 | 25 | 268 | 114 KB | +92 conduyt-js examples (single, multi-turn, Arduino-override, API docs) |
| v3 | 329 | 35 | 364 | 135 KB | +96 Arduino-vs-conduyt-js contrast (side-by-side, disambiguation, dont-mix) |
| v4 | 432 | 47 | 479 | 180 KB | +115 hardware/electronics breadth (fundamentals, sensors, actuators, debug, projects) |
| v5 | 453 | 49 | 502 | 215 KB | +23 mascarade imports (MIT): bare-metal ARM/RISC-V/STM32, FreeRTOS, FOC |

## v1 vs v2: the original failure mode

The v1 fine-tune (151 examples, r=16, 3 epochs) shipped end-to-end (Kaggle -> GGUF -> MLC -> browser inference) but produced incorrect conduyt-js code: it hallucinated a `device.arduino.*` namespace, mixed Arduino C++ idioms (`millis`, `delay`, `map`) into JS responses, and lost API consistency across multi-turn conversations.

Diagnosis: only ~12% of v1 training data was conduyt-js, all single-turn. The base Qwen2.5-Coder-1.5B's Arduino prior is heavily encoded; r=16 over 3 epochs wasn't enough to override it.

v2 fix: +93 conduyt-js examples grounded in actual `../conduyt/sdk/js/src/` source, r=32, 5 epochs, dropout=0. Results showed improvement but the model still occasionally projected Arduino primitives into JS code.

## v3: contrastive learning to teach the boundary

v2 added more conduyt-js volume; the model still mashed Arduino into JS. v3 diagnosed the gap: the model had two strong priors (Arduino looks like X, JavaScript looks like Y) and zero contrastive supervision on which one to project for which prompt.

96 contrastive examples added in v3 with five distinct system prompts:
- Arduino-only system prompt anchors pure C++ output.
- conduyt-js-only system prompt forbids Arduino primitives in JS.
- Side-by-side prompt asks for both with labeled blocks.
- Disambiguation classifier ("is this Arduino or conduyt-js?").
- Dont-mix hardening (system says no Arduino in JS; user asks JS task; assistant uses setTimeout, not delay).

After v3, expect: `device.pin(N).mode('output')`, `for await (const v of device.pin('A0').subscribe({ intervalMs: 100 }))`, `import { ConduytServo } from 'conduyt-js/modules/servo'`, no `device.arduino.*` hallucinations.

## v4: domain breadth

v3 fixed the framework boundary. v4 fills the hardware-knowledge gap: the model now answers component selection, circuit recipes, debug walkthroughs, project archetypes, and per-board hardware facts in concrete numbers and part names. 115 examples across 10 buckets.

## v5: mascarade imports

23 hand-curated examples from `electron-rare/mascarade` (MIT, attribution in `THIRD_PARTY.md`) extend coverage to bare-metal ARM Cortex-M4 + RISC-V + Pi + Teensy startup, STM32F4 LL drivers DMA + ADC, ESP-IDF MQTT + TLS + auto-reconnect with full FreeRTOS task structure, ESPAsyncWebServer REST APIs, custom PlatformIO `board.json`, BLDC FOC with Clarke and Park transforms in C, half-bridge gate driver thermal calc.

---

# Troubleshooting

See `kaggle/README.md` for failure modes, pin rationale, and platform quirks.

## Project rules

See `tracking/handoffs/` for session history and `data/seeds/` for the hand-curated training content.
