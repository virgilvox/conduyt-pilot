#!/usr/bin/env python3
"""Deduplicate examples across one or more JSONL files.

Default: exact dedup using a normalized hash of the user message.
Optional: --semantic enables near-duplicate detection via sentence-transformers
(all-MiniLM-L6-v2). Pairs above the cosine threshold drop the second occurrence.

Usage:
  python scripts/03_dedupe_dataset.py data/processed/all.jsonl --out data/processed/dedup.jsonl
  python scripts/03_dedupe_dataset.py data/processed/all.jsonl --out data/processed/dedup.jsonl --semantic --threshold 0.92
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path


def norm_user(text: str) -> str:
    n = unicodedata.normalize("NFKC", text).lower().strip()
    n = re.sub(r"\s+", " ", n)
    return n


def exact_hash(text: str) -> str:
    return hashlib.sha256(norm_user(text).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--semantic", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.92)
    args = ap.parse_args()

    seen: set[str] = set()
    kept_objs: list[dict] = []
    total = 0
    exact_drops = 0

    for path in args.inputs:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                obj = json.loads(line)
                user_text = obj["messages"][1]["content"]
                h = exact_hash(user_text)
                if h in seen:
                    exact_drops += 1
                    continue
                seen.add(h)
                kept_objs.append(obj)

    semantic_drops = 0
    if args.semantic and len(kept_objs) > 1:
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            print(
                "sentence-transformers not installed; run `uv sync --extra semantic`",
                file=sys.stderr,
            )
            return 2

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        texts = [norm_user(o["messages"][1]["content"]) for o in kept_objs]
        embs = model.encode(texts, convert_to_tensor=True, show_progress_bar=True)
        sim = util.cos_sim(embs, embs)

        keep_mask = [True] * len(kept_objs)
        for i in range(len(kept_objs)):
            if not keep_mask[i]:
                continue
            for j in range(i + 1, len(kept_objs)):
                if keep_mask[j] and float(sim[i, j]) >= args.threshold:
                    keep_mask[j] = False
                    semantic_drops += 1
        kept_objs = [o for o, m in zip(kept_objs, keep_mask) if m]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as fout:
        for obj in kept_objs:
            fout.write(json.dumps(obj) + "\n")

    print(f"input examples:    {total}")
    print(f"exact duplicates:  {exact_drops}")
    if args.semantic:
        print(f"near-duplicates:   {semantic_drops} (cos >= {args.threshold})")
    print(f"kept:              {len(kept_objs)}")
    print(f"output:            {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
