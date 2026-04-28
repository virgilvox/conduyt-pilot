#!/usr/bin/env python3
"""Validate a JSONL training file.

Checks:
  1. Every line is valid JSON.
  2. Each example has messages: [system, user, assistant] in that order.
  3. Code fences inside assistant messages are balanced.
  4. No banned phrases (em dashes, "delve into", emojis, etc).
  5. Approximate token count <= 4096 per example (cl100k tokenizer as a stand-in).
  6. No duplicate user messages within the file.

Outputs:
  - A per-rule violation count to stderr.
  - Cleaned (passing-only) lines written to data/processed/<input_basename>_clean.jsonl.

Usage:
  python scripts/02_validate_dataset.py data/seeds/*.jsonl
  python scripts/02_validate_dataset.py data/raw/synthetic_*.jsonl --token-limit 4096
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# Banned substrings; checked case-insensitively against the joined message text.
BANNED_SUBSTRINGS: list[str] = [
    "—",                # em dash (U+2014)
    "–",                # en dash (U+2013) used as em dash
    "delve into",
    "delve in to",
    "let's explore",
    "let us explore",
    "dive deep",
    "dive into",
    "in this article",
    "in this post",
    "unleash",
    "harness the power",
    "elevate your",
    "seamless",
    "cutting-edge",
    "in today's fast-paced",
    "it's not just",
    "this isn't just",
]

# Anything in the Emoji_Presentation / Extended_Pictographic class is banned.
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # symbols & pictographs (extended)
    "\U0001F600-\U0001F64F"   # emoticons
    "\U0001F900-\U0001F9FF"   # supplemental symbols
    "☀-➿"            # dingbats / misc symbols
    "]"
)

# Reasonable cl100k-ish proxy: 1 token ~= 4 chars. We don't need exactness here;
# we just want to flag examples that are clearly oversized.
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def normalize_user_text(text: str) -> str:
    """Hash key for intra-file dup detection."""
    n = unicodedata.normalize("NFKC", text).lower().strip()
    n = re.sub(r"\s+", " ", n)
    return hashlib.sha256(n.encode()).hexdigest()


def count_unbalanced_fences(text: str) -> int:
    """Returns the count of opening fences that lack a matching close.

    A balanced text has an even number of ``` markers.
    """
    fences = re.findall(r"```", text)
    return len(fences) % 2


def check_example(obj: dict, token_limit: int) -> list[str]:
    issues: list[str] = []

    msgs = obj.get("messages")
    if not isinstance(msgs, list) or len(msgs) != 3:
        issues.append("schema: messages != 3")
        return issues

    expected_roles = ["system", "user", "assistant"]
    actual_roles = [m.get("role") for m in msgs]
    if actual_roles != expected_roles:
        issues.append(f"schema: roles {actual_roles} != {expected_roles}")
        return issues

    for m in msgs:
        if not isinstance(m.get("content"), str) or not m["content"].strip():
            issues.append("schema: empty content")
            return issues

    joined = "\n".join(m["content"] for m in msgs)
    joined_lower = joined.lower()

    for b in BANNED_SUBSTRINGS:
        if b.lower() in joined_lower:
            issues.append(f'banned phrase: "{b}"')

    if EMOJI_RE.search(joined):
        issues.append("banned: emoji")

    assistant_text = msgs[2]["content"]
    if count_unbalanced_fences(assistant_text):
        issues.append("code fences: unbalanced ```")

    if estimate_tokens(joined) > token_limit:
        issues.append(f"size: estimated tokens > {token_limit}")

    return issues


def validate_file(path: Path, token_limit: int, out_dir: Path) -> dict:
    out_path = out_dir / f"{path.stem}_clean.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)

    rule_counts: Counter[str] = Counter()
    seen_user_hashes: set[str] = set()
    written = 0
    total = 0
    drops = 0

    with path.open() as fin, out_path.open("w") as fout:
        for lineno, raw in enumerate(fin, 1):
            raw = raw.rstrip("\n")
            if not raw.strip():
                continue
            total += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                rule_counts[f"json: parse error"] += 1
                print(f"  {path.name}:{lineno} parse error: {e}", file=sys.stderr)
                drops += 1
                continue

            issues = check_example(obj, token_limit=token_limit)

            user_text = obj["messages"][1]["content"]
            user_hash = normalize_user_text(user_text)
            if user_hash in seen_user_hashes:
                issues.append("dup: duplicate user message in this file")
            else:
                seen_user_hashes.add(user_hash)

            if issues:
                drops += 1
                for r in issues:
                    rule_counts[r] += 1
                    print(f"  {path.name}:{lineno} {r}", file=sys.stderr)
                continue

            fout.write(raw + "\n")
            written += 1

    return {
        "input": str(path),
        "output": str(out_path),
        "total": total,
        "kept": written,
        "dropped": drops,
        "rule_counts": dict(rule_counts),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a JSONL dataset file.")
    ap.add_argument("inputs", nargs="+", type=Path, help="Input .jsonl files.")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/processed"),
        help="Where to write <stem>_clean.jsonl.",
    )
    ap.add_argument("--token-limit", type=int, default=4096)
    args = ap.parse_args()

    grand_total = 0
    grand_kept = 0
    grand_drops = 0
    aggregate_rules: Counter[str] = Counter()

    for path in args.inputs:
        if not path.exists():
            print(f"missing: {path}", file=sys.stderr)
            continue
        report = validate_file(path, token_limit=args.token_limit, out_dir=args.out_dir)
        grand_total += report["total"]
        grand_kept += report["kept"]
        grand_drops += report["dropped"]
        for rule, n in report["rule_counts"].items():
            aggregate_rules[rule] += n
        print(
            f"{path.name}: total={report['total']} kept={report['kept']} "
            f"dropped={report['dropped']} -> {report['output']}"
        )

    print()
    print("=== aggregate ===")
    print(f"total examples: {grand_total}")
    print(f"kept:           {grand_kept}")
    print(f"dropped:        {grand_drops}")
    if aggregate_rules:
        print("violations:")
        for rule, n in aggregate_rules.most_common():
            print(f"  {n:>5}  {rule}")
    else:
        print("violations: none")

    return 0 if grand_drops == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
