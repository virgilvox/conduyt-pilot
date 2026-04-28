#!/usr/bin/env python3
"""Bundle train.jsonl + eval.jsonl + boards/*.json into a Kaggle dataset zip.

Output: conduyt-pilot-data-v<N>.zip in the current directory, where <N> is the
next free integer (v1, v2, ...).

The zip contains:
  metadata.json
  train.jsonl
  eval.jsonl
  boards/*.json

Usage:
  python scripts/05_build_kaggle_dataset.py
  python scripts/05_build_kaggle_dataset.py --version 3
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def next_version(workdir: Path, prefix: str) -> int:
    n = 1
    while (workdir / f"{prefix}-v{n}.zip").exists():
        n += 1
    return n


def count_lines(path: Path) -> int:
    with path.open() as f:
        return sum(1 for line in f if line.strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    ap.add_argument("--boards-dir", type=Path, default=Path("data/boards"))
    ap.add_argument("--prefix", default="conduyt-pilot-data")
    ap.add_argument("--version", type=int, default=None)
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    args = ap.parse_args()

    train = args.processed_dir / "train.jsonl"
    eval_ = args.processed_dir / "eval.jsonl"
    if not train.exists() or not eval_.exists():
        print(
            f"missing train/eval. Expected at {train} and {eval_}.\n"
            "Run scripts/04_split_train_eval.py first.",
            file=sys.stderr,
        )
        return 1
    boards = sorted(args.boards_dir.glob("*.json"))
    if not boards:
        print(f"no boards in {args.boards_dir}", file=sys.stderr)
        return 1

    version = args.version or next_version(args.out_dir, args.prefix)
    zip_path = args.out_dir / f"{args.prefix}-v{version}.zip"

    metadata = {
        "name": args.prefix,
        "version": version,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "train": count_lines(train),
            "eval": count_lines(eval_),
            "boards": len(boards),
        },
        "boards": [b.name for b in boards],
        "schema": {
            "examples": "messages: [system, user, assistant], plus optional board_id",
            "boards": "capability profile JSON; see _sources field for upstream verification",
        },
    }

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps(metadata, indent=2))
        zf.write(train, "train.jsonl")
        zf.write(eval_, "eval.jsonl")
        for b in boards:
            zf.write(b, f"boards/{b.name}")

    print(f"built {zip_path}")
    print(f"  train:  {metadata['counts']['train']} examples")
    print(f"  eval:   {metadata['counts']['eval']} examples")
    print(f"  boards: {metadata['counts']['boards']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
