# Kaggle troubleshooting + pin rationale

The full step-by-step Kaggle workflow lives in the top-level `README.md`. This file covers failure modes, why specific versions are pinned, and platform quirks discovered during v1 + v2 runs.

## Pin rationale (`train.ipynb`)

The pins come from Unsloth's own current Kaggle Qwen2.5-Coder reference notebook plus the `requires_dist` constraints in `unsloth==2026.4.8`. Newer versions on PyPI break the install:

| Package | Pinned | Why |
|---|---|---|
| `unsloth` | 2026.4.8 | Reference Kaggle notebook target. No `[kaggle-new]` extra needed in 2026. |
| `transformers` | 4.56.2 | Unsloth's reference notebook pin. Newer-than-5.5 is excluded by `requires_dist`. **Caps `huggingface_hub` at `<1.0`**, see below. |
| `trl` | 0.22.2 | Pinned via `--no-deps` so trl 1.x doesn't pull a conflicting transformers. |
| `peft` | 0.19.1 | Satisfies `peft>=0.18.0,!=0.11.0`. |
| `bitsandbytes` | 0.49.2 | Satisfies `bitsandbytes>=0.45.5,!=0.46.0,!=0.48.0`. |
| `accelerate` | 1.13.0 | Satisfies `accelerate>=0.34.1`. |
| `datasets` | 4.3.0 | Unsloth caps `datasets<4.4.0`. PyPI latest 4.8.x is OUT OF RANGE. |
| `huggingface_hub` | **unpinned** | transformers 4.56.2 caps `<1.0`; unsloth caps `>=0.34.0`. Let pip resolve (typically lands on 0.35.x). v1's pin to 1.12.0 broke the install. |

If you re-run this in 6+ months, run `pip show unsloth` first and re-derive the compatibility matrix. Don't blindly take "latest".

## Hyperparameter rationale (v2)

| Param | v1 | v2 | Why |
|---|---|---|---|
| LoRA `r` | 16 | **32** | More capacity to override the base model's Arduino prior. v1 r=16 wasn't enough. |
| `lora_alpha` | 32 | **64** | Match alpha=2*r. Standard Unsloth ratio. |
| `lora_dropout` | 0.05 | **0** | Unsloth's fast-patching kernels require dropout=0 (~2-3x speedup). At ~220 examples, dropout regularization isn't doing anything anyway. |
| `num_train_epochs` | 3 | **5** | Small dataset benefits from extra passes. ~140 gradient updates total at effective batch 8. |
| `fp16` | True | True | T4 silicon is fp16-only. Don't flip to bf16. |

## MLC wheel rationale

| Package | Use | Why |
|---|---|---|
| `mlc-llm-nightly-cpu` + `mlc-ai-nightly-cpu` | v2 | CPU wheels have no CUDA dependency. Weight conversion is arithmetic; GPU adds no value. |
| `mlc-llm-nightly-cu128` + `mlc-ai-nightly-cu128` | v1 (failed) | Had a TVM `tirx`/`s_tir` regression in 2026-04. Also failed at import time with "libcudart.so.12: cannot open shared object file". |
| `mlc-llm-nightly-cu122` + `mlc-ai-nightly-cu122` | not used | Kaggle T4 image is on CUDA 12.8; cu122 wheels mismatch. |

## WebLLM model_lib URL

Confirmed against `mlc-ai/web-llm@v0.2.82`'s `src/config.ts` (lines 290-291, 1378-1389) and HTTP-200 verified:

```
https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-1.5B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm
```

The `v0_2_80` subfolder is the WebLLM convention; the wasm itself targets the Qwen2.5-Coder-1.5B-Instruct-q4f16_1 quantization our convert step produces.

## Platform quirks (Kaggle, 2026)

**Dataset mount path is nested.** Kaggle now mounts attached Datasets at:
```
/kaggle/input/datasets/<kaggle-username>/<dataset-slug>/
```
Not the legacy `/kaggle/input/<slug>/`. The train notebook uses `glob.glob("/kaggle/input/**/train.jsonl", recursive=True)` to handle either form. Don't hardcode either; if Kaggle changes the layout again, the recursive glob still wins.

Kaggle username may differ from your HF username. The dataset path uses the kaggle one; HF push targets use your HF user.

**Pip entry-point scripts aren't on PATH.** `pip install`-ing a package with a CLI entry point (e.g. `mlc_llm`, `huggingface-cli`, `accelerate`) does NOT make the script available as a shell command. Always invoke via `python -m <package>` from `!`-shell cells:

```python
!python -m mlc_llm convert_weight ...   # works
!mlc_llm convert_weight ...             # FAILS: 'mlc_llm: command not found'
```

**Pre-installed package warnings are noise.** When you install training packages, you'll see warnings about `bigframes`, `s3fs`, `gcsfs`, `fsspec` having internal version conflicts. None of these are in our import path. Ignore.

## Failure modes

### Install fails with "Cannot install huggingface_hub==1.12.0 and transformers==4.56.2"
v1 had this. Drop the `huggingface_hub` pin. Already fixed in v2.

### "bf16 is not supported on this device"
T4 silicon is fp16-only. The notebook hard-codes `bf16=False` and `fp16=True`. Don't flip them.

### Unsloth warns "patched 28 layers with 0 QKV / 0 O / 0 MLP"
You have `lora_dropout > 0`. Set it to `0` to enable fast-patching kernels. Already fixed in v2.

### `FileNotFoundError: /kaggle/input/conduyt-pilot-data/train.jsonl`
The dataset isn't where the cell expects. The auto-discover cell handles arbitrary nesting under `/kaggle/input/`; if it still can't find train.jsonl, run `!find /kaggle/input/ -type f | head` to see what's actually attached.

### OOM during `save_pretrained_merged` or `save_pretrained_gguf`
The merge spikes RAM near the T4 ceiling. If it dies:
1. Restart the kernel.
2. Re-run from the merge cell only (skip re-training; the LoRA adapter is already on HF from the earlier `push_to_hub`).
3. If still OOM, re-load the adapter via `FastLanguageModel.from_pretrained(MODEL_NAME)` + `model.load_adapter(ADAPTER_REPO)` instead of holding both training-state and merge in memory.

### `save_pretrained_gguf` errors with "convert.py not found"
Unsloth caches a vendored llama.cpp on first run. If the cache fails to populate:
```bash
cd /kaggle/working
git clone https://github.com/ggerganov/llama.cpp
```
Then re-run the cell.

### MLC convert_weight: `ValueError: Callback arg cannot be RawStr`
TVM `tirx`/`s_tir` regression in cu128 nightlies (2026-04). Switch to CPU wheels (`mlc-{llm,ai}-nightly-cpu`). Already fixed in v2.

### MLC convert_weight: `OSError: libcudart.so.12: cannot open shared object file`
TVM in the cu* nightlies tries to load CUDA runtime at import time even with `--device cpu`. Switch to CPU wheels. Already fixed in v2.

### `mlc_llm: command not found`
Kaggle's PATH doesn't pick up pip entry-point scripts. Use `python -m mlc_llm`. Already fixed in v2.

### MLC `convert_weight` produces only ~11 MB of output (no `params_shard_*.bin`)
The convert step errored silently and only `gen_config` ran. Re-run convert_weight without `-q` to see the actual error. Common cause: TVM nightly bug; switch to CPU wheels.

### MLC `gen_config` complains about quantization name
MLC v0.x quantizations are `q4f16_1`, `q4f32_1`, `q0f16`, `q0f32`. Don't use `q4_k_m` here (that's a GGUF-only format).

### `HF_TOKEN` not found
Verify Add-ons -> Secrets in the Kaggle notebook (not the dataset). Secret name must be exactly `HF_TOKEN`.

### `push_to_hub` 403
Token is read-only. Generate a new one with **Write** scope at https://huggingface.co/settings/tokens.
