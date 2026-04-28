# Handoff: 2026-04-27 (session 2) — Phase 1 closed + Phase 2 shipped

Supersedes the earlier same-day handoff (`2026-04-27_phase1-scaffold.md`). That one ended at "scaffolded but no synthetic examples"; this one ends at "Kaggle bundle built, training notebooks ready".

## Pivot from session 1

Session 1 left the synthesis script as an Anthropic API wrapper around `claude-opus-4-7` and stopped before spending tokens. Session 2 resolved this by **using Claude as the synthesizer directly** in-conversation, no API calls needed. The script `scripts/01_generate_synthetic.py` still exists for future API-driven scaling, but the corpus that ships with v1 of the dataset is half hand-curated seeds (90) plus half hand-written synthetic (61) for **151 total examples**, all written by Claude in this conversation.

## Final Phase 1 corpus

```
data/processed/train.jsonl  : 137 examples
data/processed/eval.jsonl   :  14 examples
data/boards/*.json          :   8 board profiles
conduyt-pilot-data-v1.zip   : ~190 KB, 11 files
```

**By board:**
| board | count |
|---|---|
| esp32-s3-devkitc-1 | 63 |
| raspberry-pi-pico | 26 |
| adafruit-feather-esp32-s3 | 15 |
| adafruit-feather-nrf52840-sense | 11 |
| arduino-uno-r4-wifi | 10 |
| seeed-xiao-esp32-c3 | 10 |
| raspberry-pi-pico-w | 9 |
| arduino-nano-33-ble | 7 |

**By framework (heuristic):** arduino 100, conduyt-js 18, platformio 17, esp-idf 16.

ESP32-S3 DevKitC-1 is the workhorse with 63 examples; this is intentional since it's the densest cell of the test matrix (full feature set + the natural target for ESP-IDF + Conduyt-firmware coverage).

**Validation report:** all 151 examples pass the validator with **zero violations** across schema, banned-phrase, code-fence, token-size, and intra-file dedup checks.

**Cross-file dedup:** 0 exact duplicates removed. Semantic dedup not run (would require `pip install --extra semantic`).

## Files added this session

### Phase 1 finishers
- `data/raw/synthetic_20260427T202243Z.jsonl` (61 examples)
- `data/processed/{all,dedup,train,eval}.jsonl` plus per-source `*_clean.jsonl`
- `conduyt-pilot-data-v1.zip` at repo root

### Phase 2 deliverables
- `kaggle/train.ipynb` — 14-cell notebook for Kaggle T4 x2:
  - pinned installs (unsloth 2026.4.8, transformers 4.56.2, trl 0.22.2 --no-deps, peft 0.19.1, bitsandbytes 0.49.2, accelerate 1.13.0, datasets 4.3.0, huggingface_hub 1.12.0)
  - secrets via `UserSecretsClient`
  - dataset mount at `/kaggle/input/conduyt-pilot-data/`
  - QLoRA r=16, alpha=32, all attention + MLP target modules
  - Qwen2.5 chat template via `tokenizer.apply_chat_template`
  - SFTTrainer: bs=2, grad_accum=4 (effective 8), 3 epochs, 2e-4 LR, fp16 (T4 forced), adamw_8bit, linear LR
  - sanity inference (5 hardcoded probes)
  - `save_pretrained_merged` at `merged_16bit`
  - GGUF export at q4_k_m / q5_k_m / q8_0 to `virgilvox/conduyt-pilot-1.5b-gguf`
- `kaggle/convert_mlc.ipynb` — separate notebook for MLC conversion:
  - cu122 nightly wheels (`mlc-llm-nightly-cu122`, `mlc-ai-nightly-cu122`) for Kaggle T4
  - `mlc_llm convert_weight` + `mlc_llm gen_config` with `q4f16_1` and `--conv-template qwen2`
  - upload to `virgilvox/conduyt-pilot-1.5b-MLC`
  - WebLLM `appConfig` snippet with the verified Qwen2.5-Coder-1.5B-Instruct-q4f16_1 wasm URL from `mlc-ai/binary-mlc-llm-libs/main/web-llm-models/v0_2_80/Qwen2-1.5B-Instruct-q4f16_1-ctx4k_cs1k-webgpu.wasm`
- `kaggle/README.md` — full step-by-step Kaggle workflow + troubleshooting
- `scripts/06_test_local.py` — `llama-cpp-python==0.3.21` with `Llama.from_pretrained(repo_id, filename="*Q4_K_M*.gguf")` running 5 probes + 10 random eval prompts side-by-side against base + finetune; writes a markdown report to `tracking/notes/local_eval_results.md`

## Key research outputs (used as citations in Phase 2 files)

- **Unsloth Kaggle install pattern in 2026:** plain `pip install unsloth` (no `[kaggle-new]` extra anymore). Source: Unsloth's own `notebooks/nb/Kaggle-Qwen2.5_Coder_(1.5B)-Tool_Calling.ipynb`.
- **datasets cap:** unsloth 2026.4.8 pins `datasets<4.4.0`; PyPI latest 4.8.5 is out of range. Pinned to 4.3.0.
- **MLC package names:** are CUDA-suffixed in 2026; cu122 still on PyPI for T4. Use `pip install --pre -U -f https://mlc.ai/wheels mlc-llm-nightly-cu122 mlc-ai-nightly-cu122`. If Kaggle moves to CUDA 12.8 swap to `-cu128`.
- **WebLLM model_lib URL:** confirmed against `mlc-ai/web-llm@v0.2.82` `src/config.ts`; uses the `v0_2_80` subfolder of `binary-mlc-llm-libs`.
- **GGUF method names:** lowercase `q4_k_m`, `q5_k_m`, `q8_0` are what Unsloth's docs show; the API also accepts uppercase but lowercase is canonical.

## Phase 1 deliverables checklist (final)

- [x] All 8 board JSONs with verified pinouts and source citations
- [x] All 9 seed JSONLs, 90 hand-curated examples
- [x] 61 hand-written synthetic examples (no API spend)
- [x] 151 total examples, 137 train + 14 eval
- [x] Validation report shows zero violations
- [x] `conduyt-pilot-data-v1.zip` ready to upload to Kaggle

## Phase 2 deliverables checklist

- [x] `kaggle/train.ipynb` written, JSON-validated, structured to run end-to-end on Kaggle T4 x2
- [x] `kaggle/convert_mlc.ipynb` written, JSON-validated
- [x] `kaggle/README.md` with full workflow + troubleshooting
- [x] `scripts/06_test_local.py` compiles
- [ ] **Not yet executed on Kaggle.** None of the notebooks have been run; the train/eval split is small (137 train), so first run should validate the wall-time estimate (the spec says <90 min) on real hardware before scaling up.
- [ ] HF repos `virgilvox/conduyt-pilot-1.5b-{lora,gguf,merged,MLC}` not yet created. Notebooks will create them on first run.

## What I'd want a future session to do first

1. **Replace `virgilvox` with the actual HF user.** Search across `kaggle/train.ipynb`, `kaggle/convert_mlc.ipynb`, `kaggle/README.md`, `scripts/06_test_local.py`. (Or keep `virgilvox` if that's the intended account.)
2. **Run `train.ipynb` once** with the v1 dataset to confirm wall time and that the GGUF export works. Spot-check the 5 inference probes against the seeds for "is the voice shifting?" eyeball test.
3. **Push the merged model to HF** before running `convert_mlc.ipynb` (the convert notebook expects to `snapshot_download` from `MERGED_REPO`, since its kernel won't share `/kaggle/working/` with the train notebook unless you run them in the same session).
4. **Consider a v2 dataset.** 137 train is light. The corpus is well-targeted, but if the eyeball test on v1 looks marginal, the next step is to push the synthetic count to 200+ via either another in-conversation generation pass or by running `scripts/01_generate_synthetic.py` against the live API.

## Decisions worth carrying forward

1. **Claude-as-synthesizer is the cheaper path** when the user is already in a Claude conversation. Reserve `01_generate_synthetic.py` for fully-automated batch runs that don't have a human in the loop.
2. **Eval split underrepresents low-count boards.** With <10 examples per board the splitter assigns 0 eval; this is a conscious choice (a 1-example eval set per board would be noisier than just letting train carry those boards). Re-evaluate after any v2 corpus expansion.
3. **fp16=True is non-negotiable on T4.** Notebook hard-codes `bf16=False` to prevent confused future readers from flipping it.
4. **Unsloth pin discipline.** The version cliff is real; transformers 5.x silently breaks Unsloth. Stick to the matrix unless you're prepared to test.
5. **Don't co-locate MLC and Unsloth in one notebook.** Their CUDA wheels disagree.

## Open questions

- Which HF account hosts the production artifacts? Spec lists `virgilvox` placeholder; confirm before first push.
- Do you want a v2 corpus pass (more synthetic) before the first Kaggle run, or run on v1 first to validate the pipeline end-to-end on a tiny dataset?
