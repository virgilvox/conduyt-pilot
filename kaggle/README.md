# Kaggle workflow (Phase 2)

Run the fine-tune on Kaggle's free T4 x2 tier, push the result to HF Hub as a LoRA adapter, GGUF, and MLC bundle.

## 1. Build the dataset zip locally

After Phase 1 finishes (`scripts/05_build_kaggle_dataset.py`), you'll have a `conduyt-pilot-data-v<N>.zip` in the repo root.

## 2. Upload to Kaggle as a private Dataset

- New Dataset, upload the zip, set visibility Private.
- Dataset slug: `conduyt-pilot-data` (the train notebook expects `/kaggle/input/conduyt-pilot-data/...`). If your Kaggle username is `virgilvox`, the full slug becomes `virgilvox/conduyt-pilot-data`.
- Bump the dataset version each time you regenerate.

## 3. Configure secrets

Kaggle notebook -> right panel -> Add-ons -> Secrets:

| Secret | Required | Use |
|---|---|---|
| `HF_TOKEN` | yes | Push adapter, GGUF, MLC repos. Needs **write** scope. |
| `WANDB_API_KEY` | optional | Run logging. Skip and `report_to` falls back to `none`. |

## 4. Set up the train notebook

- Upload `kaggle/train.ipynb` (or paste cells).
- Right panel:
  - **Accelerator:** GPU T4 x2 (free tier).
  - **Internet:** ON.
  - **Persistence:** ON (so checkpoints survive a kernel restart).
- **Add input:** the Kaggle dataset you uploaded in step 2.
- **Edit the HF repo names** in cells that push to `virgilvox/...` to your own HF user. Search the notebook for `virgilvox` and replace.

## 5. Run all

Expected wall time on T4 x2: roughly 30 to 60 minutes for ~150 examples x 3 epochs on the 1.5B base. Most of the time is the GGUF export at the end (`save_pretrained_gguf` runs three quantizations sequentially).

What lands at the end:
- `virgilvox/conduyt-pilot-1.5b-lora` (LoRA adapter only)
- `virgilvox/conduyt-pilot-1.5b-gguf` (Q4_K_M, Q5_K_M, Q8_0 files)
- A merged 16-bit model at `/kaggle/working/merged/` (used in the next step)

## 6. (Recommended) push the merged model to HF

Before running `convert_mlc.ipynb`, push `/kaggle/working/merged` to a private HF repo so the MLC notebook can pull it cleanly:

```python
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
api.upload_folder(
    folder_path="/kaggle/working/merged",
    repo_id="virgilvox/conduyt-pilot-1.5b-merged",
    repo_type="model",
)
```

(Add this as a one-off cell at the end of `train.ipynb` or run it in a fresh kernel against the `merged/` folder.)

## 7. Run convert_mlc.ipynb

- New Kaggle notebook, accelerator GPU T4 (single, T4 x2 not needed).
- Internet ON, Persistence ON.
- HF_TOKEN secret.
- Set `MERGED_REPO` in the notebook to the repo you pushed the merged model to.

Outputs: `virgilvox/conduyt-pilot-1.5b-MLC` plus a printed `appConfig` snippet for WebLLM.

## 8. Smoke-test locally

```bash
uv run scripts/06_test_local.py
```

Pulls the GGUF from HF, runs 5 sanity prompts + 10 from `data/processed/eval.jsonl` against both the base and the fine-tuned model side-by-side.

## Pinned dependency rationale

The pins in `train.ipynb` (unsloth 2026.4.8, transformers 4.56.2, trl 0.22.2 with --no-deps, datasets 4.3.0) come from Unsloth's own current Kaggle Qwen2.5-Coder reference notebook plus the `requires_dist` constraints in `unsloth==2026.4.8`. Newer versions on PyPI (transformers 5.x, datasets 4.4+) violate Unsloth's constraints. If you're re-running this in 6 months, run `pip show unsloth` first and re-derive the compatibility pins.

## Troubleshooting

- **"bf16 is not supported on this device"** : T4 is fp16 only. The notebook already sets `bf16=False`. Don't change it.
- **OOM on GGUF export** : the merge step runs in fp16 and can spike RAM near the T4 ceiling. If it fails, restart the kernel and run starting from cell 12 (`save_pretrained_merged`) on a clean GPU.
- **`mlc-llm-nightly-cu122` not found** : Kaggle's CUDA version may have moved to 12.8. Try `mlc-llm-nightly-cu128` and the matching `mlc-ai-nightly-cu128`.
- **`save_pretrained_gguf` errors with "convert.py not found"** : Unsloth caches a vendored llama.cpp on first run. If the cache fails to populate, manually `git clone https://github.com/ggerganov/llama.cpp` into `/kaggle/working/` and re-run.
