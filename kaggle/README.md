# Kaggle troubleshooting + pin rationale

The full step-by-step Kaggle workflow lives in the top-level `README.md`. This file covers failure modes and why specific versions are pinned.

## Pin rationale (`train.ipynb`)

The pins come from Unsloth's own current Kaggle Qwen2.5-Coder reference notebook plus the `requires_dist` constraints in `unsloth==2026.4.8`. Newer versions on PyPI break the install:

| Package | Pinned | Why |
|---|---|---|
| `unsloth` | 2026.4.8 | Reference Kaggle notebook target. No `[kaggle-new]` extra needed in 2026. |
| `transformers` | 4.56.2 | Unsloth's reference notebook pin. PyPI latest (5.x) is technically allowed by `requires_dist` but untested; newer-than-5.5 is excluded. |
| `trl` | 0.22.2 | Pinned via `--no-deps` so trl 1.x doesn't pull a conflicting transformers. |
| `peft` | 0.19.1 | Satisfies `peft>=0.18.0,!=0.11.0`. |
| `bitsandbytes` | 0.49.2 | Satisfies `bitsandbytes>=0.45.5,!=0.46.0,!=0.48.0`. |
| `accelerate` | 1.13.0 | Satisfies `accelerate>=0.34.1`. |
| `datasets` | 4.3.0 | Unsloth caps `datasets<4.4.0`. PyPI latest 4.8.x is OUT OF RANGE. |
| `huggingface_hub` | unpinned | transformers 4.56.2 caps `<1.0`; unsloth caps `>=0.34.0`. Let pip resolve (typically lands on 0.35.x). Pinning to 1.12.0 fails install. |

If you re-run this in 6+ months, run `pip show unsloth` first and re-derive the compatibility matrix. Don't blindly take "latest".

## Pin rationale (`convert_mlc.ipynb`)

| Package | Pinned | Why |
|---|---|---|
| `mlc-llm-nightly-cu122` / `mlc-ai-nightly-cu122` | latest pre-release | CUDA-suffixed packages. cu122 matches Kaggle T4's CUDA runtime in 2026. |

If Kaggle moves to CUDA 12.8 (already on some images), swap to `mlc-llm-nightly-cu128` + `mlc-ai-nightly-cu128`.

## WebLLM model_lib URL

Confirmed against `mlc-ai/web-llm@v0.2.82`'s `src/config.ts` (lines 290-291, 1378-1389) and HTTP-200 verified:

```
https://raw.githubusercontent.com/mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-1.5B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm
```

The `v0_2_80` subfolder is the WebLLM convention; the wasm itself targets the Qwen2.5-Coder-1.5B-Instruct-q4f16_1 quantization our convert step produces.

## Failure modes

### "bf16 is not supported on this device"
T4 silicon is fp16-only. The notebook hard-codes `bf16=False` and `fp16=True`. Don't flip them.

### OOM during `save_pretrained_merged` or `save_pretrained_gguf`
The merge spikes RAM near the T4 ceiling. If it dies:
1. Restart the kernel.
2. Re-run from the merge cell only (skip re-training; the LoRA adapter is already on HF from the earlier `push_to_hub` cell).
3. If still OOM, re-load the adapter via `FastLanguageModel.from_pretrained(MODEL_NAME)` + `model.load_adapter(ADAPTER_REPO)` instead of holding both training-state and merge in memory.

### `save_pretrained_gguf` errors with "convert.py not found"
Unsloth caches a vendored llama.cpp on first run. If the cache fails to populate:
```bash
cd /kaggle/working
git clone https://github.com/ggerganov/llama.cpp
```
Then re-run the cell.

### `mlc-llm-nightly-cu122` not found on PyPI
Kaggle's CUDA version moved. Check with `nvidia-smi` in a code cell; if you see CUDA 12.8, swap to `cu128` packages.

### `mlc_llm convert_weight` complains about quantization name
Quantization names in MLC v0.x: `q4f16_1`, `q4f32_1`, `q0f16`, `q0f32`. The `q4f16_1` format is what WebLLM expects; don't use `q4_k_m` here (that's a GGUF-only format).

### Notebook can't see the dataset
Verify the dataset slug is exactly `conduyt-pilot-data` (the path the train notebook hardcodes is `/kaggle/input/conduyt-pilot-data/`). If your Kaggle username prefixes the slug, the mount path is still `/kaggle/input/conduyt-pilot-data/` regardless of the owner — the slug part is what counts.

### `HF_TOKEN` not found
Verify Add-ons -> Secrets in the Kaggle notebook (not the dataset). Secret name must be exactly `HF_TOKEN`.

### `push_to_hub` 403
Token is read-only. Generate a new one with **Write** scope at https://huggingface.co/settings/tokens.
