# conduyt-pilot

Fine-tune toolkit for a small embedded-coding model. Phase 1 builds a clean training dataset of (system, user, assistant) chat triples covering 8 representative MCU boards across Arduino, PlatformIO, ESP-IDF, Conduyt firmware, and conduyt-js. Phase 2 runs an Unsloth + QLoRA fine-tune of `Qwen2.5-Coder-1.5B-Instruct` on Kaggle's free T4 x2 tier, then exports GGUF (Ollama / llama.cpp / Pi) and MLC (browser via WebLLM).

## Setup

```bash
# Python 3.11 required.
uv sync

# Optional: enable semantic dedup
uv sync --extra semantic
```

## Where things are

```
data/seeds/                  90 hand-curated examples (committed)
data/boards/                 8 board capability profiles (committed)
data/raw/                    synthetic outputs (gitignored)
data/processed/              cleaned/validated/split outputs (gitignored)
prompts/                     synthesis system + template prompts
scripts/                     pipeline (01-05) + local GGUF test (06)
kaggle/                      train.ipynb + convert_mlc.ipynb + troubleshooting
tracking/handoffs/           session handoffs
conduyt-pilot-data-v1.zip    the v1 Kaggle bundle (gitignored)
```

---

# Run the fine-tune (the part you do yourself in Kaggle)

The repo ships with `conduyt-pilot-data-v1.zip` already built (~48 KB, 151 examples). The path below uses that bundle. If you've changed seeds or added synthetic, see "Regenerate the dataset" further down.

## What's in the zip

`conduyt-pilot-data-v1.zip` has 11 files totalling ~190 KB:

```
metadata.json                                # dataset info: counts, schema, version
train.jsonl                                  # 137 chat-format examples (~160 KB)
eval.jsonl                                   #  14 chat-format examples (~16 KB)
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
ls -lh conduyt-pilot-data-v1.zip
unzip -l conduyt-pilot-data-v1.zip
```

## Step 1: get a Hugging Face write token

1. https://huggingface.co/settings/tokens -> New token
2. Type: **Write**
3. Name it something like `conduyt-pilot-kaggle`
4. Copy the `hf_...` string. You'll paste it into Kaggle Secrets in step 3.

The notebooks use this token to push four repos under your HF account on first run (they create the repos via `create_repo(exist_ok=True)`):
- `virgilvox/conduyt-pilot-1.5b-lora` (LoRA adapter)
- `virgilvox/conduyt-pilot-1.5b-merged` (merged 16-bit model, used by the MLC step)
- `virgilvox/conduyt-pilot-1.5b-gguf` (Q4_K_M, Q5_K_M, Q8_0)
- `virgilvox/conduyt-pilot-1.5b-MLC` (q4f16_1 for WebLLM)

## Step 2: upload the dataset to Kaggle

1. https://www.kaggle.com/datasets -> **New Dataset**
2. Drag `conduyt-pilot-data-v1.zip` into the upload area. Kaggle will unpack it; the dataset ends up with `train.jsonl`, `eval.jsonl`, and `boards/` as siblings.
3. **Title:** `conduyt-pilot-data` (the dataset slug must be `conduyt-pilot-data` so the notebook's `/kaggle/input/conduyt-pilot-data/` mount works)
4. **Visibility:** Private
5. Create

Bump the dataset version each time you regenerate locally and re-upload; Kaggle keeps version history.

## Step 3: create the train notebook on Kaggle

1. https://www.kaggle.com/code -> **New Notebook**
2. **File -> Import Notebook -> Upload** -> pick `kaggle/train.ipynb` from this repo
3. Right-side panel:
   - **Accelerator:** GPU T4 x2
   - **Internet:** ON
   - **Persistence:** ON
4. **Add data** (right panel) -> search for the dataset you uploaded (`conduyt-pilot-data`) -> Add. It mounts at `/kaggle/input/conduyt-pilot-data/`.
5. **Add-ons -> Secrets** (top menu):
   - Add `HF_TOKEN` with the value from step 1
   - Optional: add `WANDB_API_KEY` if you want training logs in wandb (otherwise `report_to=none`)

## Step 4: run train.ipynb

Click **Run All**. Expected wall time: ~30 to 60 minutes for 137 examples x 3 epochs on a T4.

What happens, in order:
1. Pinned installs (`unsloth==2026.4.8`, `transformers==4.56.2`, `trl==0.22.2 --no-deps`, etc.)
2. Loads `HF_TOKEN` and (optionally) `WANDB_API_KEY` from Kaggle Secrets
3. Loads `train.jsonl` + `eval.jsonl` from the mounted dataset
4. Loads `unsloth/Qwen2.5-Coder-1.5B-Instruct` in 4-bit
5. Applies LoRA (r=16, alpha=32, all attention + MLP target modules)
6. Formats with the Qwen2.5 chat template
7. Trains with SFTTrainer (batch 2, grad-accum 4, 3 epochs, fp16)
8. Saves the LoRA adapter to `/kaggle/working/adapter` and pushes it to `virgilvox/conduyt-pilot-1.5b-lora`
9. Runs 5 sanity inference probes (eyeball the output here)
10. Merges LoRA into the base weights and saves the full-precision model to `/kaggle/working/merged`
11. Exports GGUF at q4_k_m / q5_k_m / q8_0 and pushes the three files to `virgilvox/conduyt-pilot-1.5b-gguf`

When it finishes, you'll have the LoRA + GGUF on HF, and the merged model still sitting at `/kaggle/working/merged` inside the kernel.

## Step 5: bridge train -> MLC (push the merged model to HF)

The MLC convert notebook runs in a fresh kernel that can't see `/kaggle/working/merged` from the train kernel. Push the merged model to HF before moving on.

In the train notebook, add a final cell (or run it in the same kernel after step 4 finishes):

```python
from huggingface_hub import HfApi, create_repo
import os

MERGED_REPO = "virgilvox/conduyt-pilot-1.5b-merged"
api = HfApi(token=os.environ["HF_TOKEN"])
create_repo(MERGED_REPO, exist_ok=True, token=os.environ["HF_TOKEN"], private=True)
api.upload_folder(
    folder_path="/kaggle/working/merged",
    repo_id=MERGED_REPO,
    repo_type="model",
)
print("merged pushed to https://huggingface.co/" + MERGED_REPO)
```

## Step 6: run convert_mlc.ipynb

1. https://www.kaggle.com/code -> **New Notebook** -> Import `kaggle/convert_mlc.ipynb`
2. Accelerator: **GPU T4** (single is fine; conversion is mostly CPU-bound)
3. Internet: ON, Persistence: ON
4. Add-ons -> Secrets -> `HF_TOKEN` (same token as before)
5. **Run All**. Wall time: ~10 to 15 minutes (most of it is the upload).

This produces:
- `virgilvox/conduyt-pilot-1.5b-MLC` on HF (weights + config for WebLLM)
- A printed `appConfig` snippet for `@mlc-ai/web-llm`. Drop it into your client-side bootstrap.

## Step 7: smoke-test the GGUF locally

Back on your machine:

```bash
uv sync
uv run scripts/06_test_local.py
```

This pulls the Q4_K_M GGUF from `virgilvox/conduyt-pilot-1.5b-gguf` and the matching base GGUF from Qwen, runs 5 hardcoded probes plus 10 random prompts from `data/processed/eval.jsonl`, and writes a side-by-side comparison report to `tracking/notes/local_eval_results.md`.

If the fine-tuned column reads in your voice and the base column reads like generic LLM output, the train worked.

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
| `virgilvox/conduyt-pilot-1.5b-gguf` | `ollama create conduyt -f Modelfile && ollama run conduyt`. Or `llama.cpp` directly. Or LM Studio. |
| `virgilvox/conduyt-pilot-1.5b-MLC` | Browser inference with WebGPU via `@mlc-ai/web-llm`. |
| `virgilvox/conduyt-pilot-1.5b-lora` | Low-storage distribution: anyone with the base model can apply this 30 MB adapter. |
| `virgilvox/conduyt-pilot-1.5b-merged` | Anywhere HF transformers / vLLM runs. |

---

# Regenerate the dataset (only if you've changed seeds or want more synthetic)

The pipeline is five scripts, each writing a typed output:

```bash
# 1. (optional) Generate more synthetic via the live Anthropic API.
#    Skip this if you'd rather have Claude Code generate examples in-conversation.
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

---

# Troubleshooting

See `kaggle/README.md` for failure modes specific to Kaggle (T4 fp16 quirks, OOM during merge, MLC CUDA wheel mismatches).

## Project rules

See `CLAUDE.md` for engineering rules and voice rules. See `tracking/handoffs/` for session history.
