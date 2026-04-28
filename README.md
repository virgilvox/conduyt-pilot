# conduyt-pilot

Phase 1 dataset toolkit for the conduyt fine-tune pilot. Builds a clean training corpus of embedded-coding examples (Arduino, PlatformIO, ESP-IDF, conduyt-js) covering 8 representative MCU boards.

## Setup

```bash
# Requires Python 3.11
uv sync                  # install runtime deps
uv sync --extra semantic # add sentence-transformers for near-dup detection

export ANTHROPIC_API_KEY=sk-ant-...
```

## Dataset workflow

```
data/seeds/        committed, hand-curated canonical examples (~90 lines)
   |
   |  data/boards/*.json (committed capability profiles)
   |
   v
scripts/01_generate_synthetic.py   --> data/raw/synthetic_<ts>.jsonl
scripts/02_validate_dataset.py     --> data/processed/<name>_clean.jsonl + report
scripts/03_dedupe_dataset.py       --> data/processed/dedup.jsonl
scripts/04_split_train_eval.py     --> data/processed/{train,eval}.jsonl
scripts/05_build_kaggle_dataset.py --> conduyt-pilot-data-v<N>.zip
```

## Smoke-test commands

```bash
# 1. Inspect what the generator would send without spending tokens
uv run scripts/01_generate_synthetic.py --dry-run

# 2. Generate a small sample
uv run scripts/01_generate_synthetic.py --limit 50 --max-cost-usd 0.50

# 3. Validate (run against seeds first to verify the rules)
uv run scripts/02_validate_dataset.py data/seeds/*.jsonl
uv run scripts/02_validate_dataset.py data/raw/synthetic_*.jsonl

# 4. Combine all clean files, dedupe, split
cat data/processed/*_clean.jsonl > data/processed/all.jsonl
uv run scripts/03_dedupe_dataset.py data/processed/all.jsonl --out data/processed/dedup.jsonl
uv run scripts/04_split_train_eval.py data/processed/dedup.jsonl

# 5. Bundle for Kaggle upload
uv run scripts/05_build_kaggle_dataset.py
```

## Targeted full run

After smoke-test passes:

```bash
# ~390 examples (90 seed + 300 synthetic), $0.50 - $2 estimated cost
uv run scripts/01_generate_synthetic.py --limit 300 --max-cost-usd 2.50
```

## Project rules

See `CLAUDE.md` for engineering and voice rules. See `tracking/handoffs/` for session history.
