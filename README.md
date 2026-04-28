# conduyt-pilot

Fine-tune toolkit for a small embedded-coding model. Phase 1 builds a clean training dataset of (system, user, assistant) chat triples covering 8 representative MCU boards across Arduino, PlatformIO, ESP-IDF, Conduyt firmware, and conduyt-js. Phase 2 runs an Unsloth + QLoRA fine-tune of `Qwen2.5-Coder-1.5B-Instruct` on Kaggle's free T4 x2 tier, then exports GGUF (Ollama / llama.cpp / Pi) and MLC (browser via WebLLM).

**The current corpus** (`conduyt-pilot-data-v2.zip`, 268 examples):
- 151 hand-curated v1 seed + synthetic examples (Arduino, PlatformIO, ESP-IDF, NeoPixel, I2C, SPI, conduyt firmware, conduyt-js, ESP32 WiFi)
- 92 v2 conduyt-js batches: 30 single-turn (every transport/module/error class), 32 multi-turn conversations, 20 Arduino-vocab override examples, 10 API doc-style Q&A
- 25 doc-derived examples extracted from `../conduyt/site/content/docs/` (concepts, how-to, modules with code stripped, reference, tutorials) via `scripts/07_extract_conduyt_docs.py`

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
conduyt-pilot-data-v2.zip    the current Kaggle bundle (gitignored)
```

---

# Run the fine-tune (the part you do yourself in Kaggle)

The repo ships with `conduyt-pilot-data-v2.zip` already built (~290 KB, 243 examples).

## What's in the zip

```
metadata.json                               # dataset info: counts, schema, version
train.jsonl                                 # 243 chat-format examples
eval.jsonl                                  #  25 chat-format examples
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
ls -lh conduyt-pilot-data-v2.zip
unzip -l conduyt-pilot-data-v2.zip
```

## Step 1: get a Hugging Face write token

1. https://huggingface.co/settings/tokens -> New token
2. Type: **Write**
3. Name it something like `conduyt-pilot-kaggle`
4. Copy the `hf_...` string. You'll paste it into Kaggle Secrets in step 3.

The notebooks push to four HF repos under `virgilvox/` on first run (they use `create_repo(exist_ok=True)`):
- `virgilvox/conduyt-pilot-1.5b-v2-lora` (LoRA adapter)
- `virgilvox/conduyt-pilot-1.5b-v2-merged` (merged 16-bit, used by the MLC step)
- `virgilvox/conduyt-pilot-1.5b-v2-gguf` (Q4_K_M, Q5_K_M, Q8_0)
- `virgilvox/conduyt-pilot-1.5b-v2-MLC` (q4f16_1 for WebLLM)

## Step 2: upload the dataset to Kaggle

1. https://www.kaggle.com/datasets -> **New Dataset**
2. Drag `conduyt-pilot-data-v2.zip` into the upload area. Kaggle will unpack it.
3. **Title:** `conduyt-pilot-data` (the dataset slug must be `conduyt-pilot-data`)
4. **Visibility:** Private
5. Create

**Heads-up about the mount path:** Kaggle in 2026 mounts attached datasets at `/kaggle/input/datasets/<your-kaggle-username>/<slug>/`, not the legacy `/kaggle/input/<slug>/`. The train notebook auto-discovers either layout via `glob /kaggle/input/**/train.jsonl`, so you don't need to hardcode the path. If you change the auto-discover logic, remember the path includes your kaggle username, which can differ from your HF username.

## Step 3: create the train notebook on Kaggle

1. https://www.kaggle.com/code -> **New Notebook**
2. **File -> Import Notebook -> Upload** -> pick `kaggle/train.ipynb` from this repo
3. Right-side panel:
   - **Accelerator:** GPU T4 x2
   - **Internet:** ON
   - **Persistence:** ON
4. **Add data** (right panel) -> search for the dataset you uploaded (`conduyt-pilot-data`) -> Add.
5. **Add-ons -> Secrets** (top menu):
   - Add `HF_TOKEN` with the value from step 1
   - Optional: `WANDB_API_KEY` for run logging
6. **Edit the HF repo names** if your HF user isn't `virgilvox`. Search the notebook for `virgilvox` and replace.

## Step 4: run train.ipynb

Click **Run All**. Expected wall time on T4 x2: roughly **45-75 minutes** for 243 examples × 5 epochs on the 1.5B base. v2 takes longer than v1 (which was 30-60 min) because of more data and more epochs.

What happens, in order:
1. Pinned installs (`unsloth==2026.4.8`, `transformers==4.56.2`, `trl==0.22.2 --no-deps`, etc.). `huggingface_hub` is intentionally NOT pinned (transformers 4.56.2 caps it at `<1.0`; v1's pin to 1.12.0 broke the install).
2. Loads `HF_TOKEN` and (optionally) `WANDB_API_KEY` from Kaggle Secrets.
3. **Auto-discovers** the dataset path under `/kaggle/input/**/train.jsonl`.
4. Loads `unsloth/Qwen2.5-Coder-1.5B-Instruct` in 4-bit.
5. Applies LoRA: `r=32, lora_alpha=64, dropout=0` (v2; was 16/32/0.05 in v1). Bigger r gives more override capacity against the base model's Arduino prior. dropout=0 enables Unsloth's fast-patching kernels (~2-3x faster than dropout>0).
6. Formats with the Qwen2.5 chat template via `tokenizer.apply_chat_template`.
7. Trains with SFTTrainer: bs=2, grad-accum=4 (effective 8), **5 epochs** (was 3), 2e-4 LR, fp16 (T4-required).
8. Saves the LoRA adapter to `/kaggle/working/adapter` and pushes it to `virgilvox/conduyt-pilot-1.5b-v2-lora`.
9. Runs 5 sanity inference probes (eyeball the output here for voice + API correctness).
10. Merges LoRA into the base weights and saves at `/kaggle/working/merged`.
11. Exports GGUF at q4_k_m / q5_k_m / q8_0 and pushes the three files to `virgilvox/conduyt-pilot-1.5b-v2-gguf`.
12. **Auto-pushes the merged model** to `virgilvox/conduyt-pilot-1.5b-v2-merged`. This bridges to `convert_mlc.ipynb`, which runs in a fresh kernel that can't see `/kaggle/working/`.

When it finishes you'll have lora + gguf + merged on HF, ready for the MLC step.

## Step 5: run convert_mlc.ipynb

1. https://www.kaggle.com/code -> **New Notebook** -> Import `kaggle/convert_mlc.ipynb`
2. Accelerator: **GPU T4** (single is fine; we use CPU MLC wheels anyway)
3. Internet: ON, Persistence: ON
4. Add-ons -> Secrets -> `HF_TOKEN`
5. **Run All**. Wall time: ~10-15 minutes (most is the upload).

**Three known fixes baked in:**
- **CPU-only MLC wheels** (`mlc-{llm,ai}-nightly-cpu`) instead of cu* variants. The cu128 nightlies in 2026-04 had a TVM `tirx`/`s_tir` regression and a `libcudart.so.12` link issue at import time. CPU wheels have no CUDA dep and just work.
- **`python -m mlc_llm`** invocation instead of bare `mlc_llm`. Kaggle's PATH doesn't pick up pip entry-point scripts.
- **`--device cpu`** for `convert_weight`. The math is the same; this side-steps the CUDA codepath that was crashing.

This produces:
- `virgilvox/conduyt-pilot-1.5b-v2-MLC` on HF (weights + config for WebLLM)
- A printed `appConfig` snippet for `@mlc-ai/web-llm`. Drop it into your client-side bootstrap.

## Step 6: smoke-test the GGUF locally

Back on your machine:

```bash
uv sync
uv run scripts/06_test_local.py --finetune-repo virgilvox/conduyt-pilot-1.5b-v2-gguf
```

This pulls the Q4_K_M GGUF from `virgilvox/conduyt-pilot-1.5b-v2-gguf` and the matching base GGUF from Qwen, runs 5 hardcoded probes plus 10 random prompts from `data/processed/eval.jsonl`, and writes a side-by-side comparison report to `tracking/notes/local_eval_results.md`.

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
| `virgilvox/conduyt-pilot-1.5b-v2-gguf` | `ollama create conduyt -f Modelfile && ollama run conduyt`. Or `llama.cpp` directly. Or LM Studio. |
| `virgilvox/conduyt-pilot-1.5b-v2-MLC` | Browser inference with WebGPU via `@mlc-ai/web-llm`. |
| `virgilvox/conduyt-pilot-1.5b-v2-lora` | Low-storage distribution: anyone with the base model can apply this ~50 MB adapter. |
| `virgilvox/conduyt-pilot-1.5b-v2-merged` | Anywhere HF transformers / vLLM runs. |

---

# Regenerate the dataset (only if you've changed seeds or want more synthetic)

The pipeline is six scripts, each writing a typed output. Note: you can have Claude Code generate synthetic examples directly in-conversation (no API spend), or run the script against the live Anthropic API.

```bash
# 1. (optional) Generate more synthetic via the live Anthropic API.
export ANTHROPIC_API_KEY=sk-ant-...
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

# v1 vs v2: what changed and why

The v1 fine-tune (151 examples, r=16, 3 epochs) shipped end-to-end (Kaggle -> GGUF -> MLC -> browser inference) but produced incorrect conduyt-js code: it hallucinated a `device.arduino.*` namespace, mixed Arduino C++ idioms (`millis`, `delay`, `map`) into JS responses, and lost API consistency across multi-turn conversations.

Diagnosis: only ~12% of v1 training data was conduyt-js, all single-turn. The base Qwen2.5-Coder-1.5B's Arduino prior is heavily encoded; r=16 over 3 epochs wasn't enough to override it.

v2 changes:
- **+93 conduyt-js-focused examples**: 30 single-turn covering every transport / module / error class, 30 multi-turn conversations where turn 2 builds on turn 1 (the exact failure mode), 20 Arduino-vocab override examples (user uses `digitalWrite`, `millis`, `delay`, etc.; assistant responds with conduyt-js API), 10 API doc-style examples.
- **All conduyt-js examples verified against `../conduyt/sdk/js/src/` source.** v1 had API drift from the README; v2 is grounded in the actual class definitions.
- **r=32, alpha=64** (was 16/32). Doubles the LoRA's override capacity.
- **5 epochs** (was 3).
- **dropout=0** (was 0.05) so Unsloth's fast-patching kernels engage.

After v2, expect the fine-tune to use the real conduyt-js API:
- `import { ConduytServo } from 'conduyt-js/modules/servo'`
- `new ConduytServo(device); await servo.attach(N); await servo.write(angle)`
- `device.pin(N).mode('output'); await device.pin(N).write(v)`
- `for await (const v of device.pin('A0').subscribe({ intervalMs: 100 }))`

---

# Troubleshooting

See `kaggle/README.md` for failure modes and pin rationale.

## Project rules

See `CLAUDE.md` for engineering rules and voice rules. See `tracking/handoffs/` for session history.
