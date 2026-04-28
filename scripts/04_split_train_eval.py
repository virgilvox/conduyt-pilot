#!/usr/bin/env python3
"""Stratified 90/10 train/eval split over examples in a JSONL file.

Stratified by `board_id` if present; otherwise random.

Usage:
  python scripts/04_split_train_eval.py data/processed/dedup.jsonl
  python scripts/04_split_train_eval.py data/processed/dedup.jsonl --eval-fraction 0.1 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path)
    ap.add_argument("--eval-fraction", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    args = ap.parse_args()

    rng = random.Random(args.seed)

    by_board: dict[str, list[dict]] = defaultdict(list)
    untagged: list[dict] = []

    with args.input.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            bid = obj.get("board_id")
            if bid:
                by_board[bid].append(obj)
            else:
                untagged.append(obj)

    train: list[dict] = []
    eval_set: list[dict] = []

    for bid, items in by_board.items():
        rng.shuffle(items)
        n_eval = max(1, int(round(len(items) * args.eval_fraction))) if len(items) >= 10 else 0
        eval_set.extend(items[:n_eval])
        train.extend(items[n_eval:])

    if untagged:
        rng.shuffle(untagged)
        n_eval = int(round(len(untagged) * args.eval_fraction))
        eval_set.extend(untagged[:n_eval])
        train.extend(untagged[n_eval:])

    rng.shuffle(train)
    rng.shuffle(eval_set)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    train_path = args.out_dir / "train.jsonl"
    eval_path = args.out_dir / "eval.jsonl"

    with train_path.open("w") as f:
        for obj in train:
            f.write(json.dumps(obj) + "\n")
    with eval_path.open("w") as f:
        for obj in eval_set:
            f.write(json.dumps(obj) + "\n")

    print(f"input:    {args.input}")
    print(f"by_board: {{ {', '.join(f'{k}: {len(v)}' for k, v in sorted(by_board.items()))} }}")
    print(f"train:    {len(train)} -> {train_path}")
    print(f"eval:     {len(eval_set)} -> {eval_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
