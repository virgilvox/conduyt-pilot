#!/usr/bin/env python3
"""Extract conduyt documentation into JSONL training examples.

Reads markdown docs from ../conduyt/site/content/docs/, strips YAML
frontmatter, normalizes em/en dashes, and emits one training example per
document.

For docs known to have API drift in their code samples (modules/, reference/
js-api), code blocks are stripped, leaving only the prose. Concept docs and
how-to guides are extracted with code blocks intact.

Each example becomes:

    system: hardware engineering assistant prompt
    user:   derived from doc title (e.g. "Explain Servo Module in conduyt.")
    assistant: cleaned doc body

Outputs to data/raw/v3_conduyt_docs.jsonl by default. After extraction, run
the validator to catch any banned-phrase or code-fence issues, then promote
the file to data/seeds/ for inclusion in the v3 corpus.

Usage:
  python scripts/07_extract_conduyt_docs.py
  python scripts/07_extract_conduyt_docs.py --docs-root ../conduyt/site/content/docs
  python scripts/07_extract_conduyt_docs.py --strip-code-from "modules/*.md"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Categories. Each entry: (glob, system_prompt_label, strip_code_default).
CATEGORIES: list[tuple[str, str, bool]] = [
    ("concepts/*.md", "concept",  False),
    ("how-to/*.md",   "how-to",   False),
    ("tutorials/*.md","tutorial", False),
    # Modules + js-api have known API drift in their code blocks.
    # Strip code; keep the prose (wiring tables, hardware notes, command refs).
    ("modules/*.md",  "module",   True),
    # Reference docs are mostly tables and protocol-level content; usually clean.
    ("reference/datastream-types.md", "reference", False),
    ("reference/error-codes.md",      "reference", False),
    ("reference/hello-resp.md",       "reference", False),
    ("reference/packet-types.md",     "reference", False),
    ("reference/packet-structure.md", "reference", False),
    # Skip these: sdks/* (not JS-focused), boards/* (we have JSON profiles),
    # firmware-api.md (C++), python-api.md (not our target), js-api.md (drift).
]

# Drift heuristics for warning the user about specific doc patterns.
DRIFT_PATTERNS: list[tuple[str, str]] = [
    (r"\bimport\s*\{\s*Servo\s*\}",                "uses 'Servo' (should be 'ConduytServo')"),
    (r"\bimport\s*\{\s*NeoPixel\s*\}",             "uses 'NeoPixel' (should be 'ConduytNeoPixel')"),
    (r"\bimport\s*\{\s*OLED\s*\}",                 "uses 'OLED' (should be 'ConduytOLED')"),
    (r"\bnew\s+Servo\s*\(",                        "uses 'new Servo(' (should be 'new ConduytServo(')"),
    (r"\bnew\s+NeoPixel\s*\(",                     "uses 'new NeoPixel(' (should be 'new ConduytNeoPixel(')"),
    (r"\bsubscribe\s*\(\s*\{\s*mode:\s*['\"]",     "uses string mode in subscribe (should be SUB_MODE.* numeric)"),
]

# Banned substrings to scrub. Same set as the validator, re-applied here so
# the extracted content lands clean by default.
BANNED_PHRASES: list[str] = [
    "delve into", "delve in to", "let's explore", "let us explore",
    "dive deep", "dive into", "in this article", "in this post",
    "unleash", "harness the power", "elevate your", "seamless",
    "cutting-edge", "in today's fast-paced", "it's not just",
    "this isn't just",
]


@dataclass
class ExtractionResult:
    examples: list[dict] = field(default_factory=list)
    drift_warnings: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def normalize_dashes(text: str) -> str:
    """Replace em/en dashes with safe punctuation."""
    text = text.replace("— ", ". ")
    text = text.replace(" —", ".")
    text = text.replace("—", ".")
    text = text.replace("– ", ". ")
    text = text.replace(" –", ".")
    text = text.replace("–", "-")
    return text


def strip_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5:]
    fm = {}
    for line in fm_text.splitlines():
        m = re.match(r'^(\w+):\s*"?(.+?)"?\s*$', line)
        if m:
            fm[m.group(1)] = m.group(2)
    return fm, body


def strip_code_blocks(body: str) -> str:
    """Remove fenced code blocks; replace with a placeholder marker."""
    return re.sub(
        r"```[^\n]*\n.*?```",
        "(code example omitted; use the host SDK API directly)",
        body,
        flags=re.DOTALL,
    )


def derive_user_prompt(fm: dict, file_path: Path, label: str) -> str:
    title = fm.get("title", "").strip().strip('"')
    if not title:
        title = file_path.stem.replace("-", " ").replace("_", " ").title()

    if label == "module":
        return f"Tell me about the conduyt {title}."
    if label == "concept":
        if title.lower().startswith("why"):
            return title + "?"
        if title.lower().startswith("the "):
            return f"Explain {title} in conduyt."
        return f"Explain conduyt's {title.lower()}."
    if label == "how-to":
        if title.lower().startswith("connect"):
            return f"How do I {title.lower()} a conduyt device?"
        if title.lower().startswith("update"):
            return f"How do I {title.lower()} on a conduyt device?"
        if title.lower().startswith("write"):
            return f"How do I {title.lower()}?"
        if title.lower().startswith("use"):
            return f"How do I {title.lower()} in conduyt?"
        return f"How do I {title.lower()}?"
    if label == "tutorial":
        return f"Walk me through {title.lower()}."
    if label == "reference":
        return f"What are the conduyt {title}?"
    return f"Explain {title}."


def detect_drift(body: str, file_path: Path) -> list[str]:
    out = []
    for pattern, msg in DRIFT_PATTERNS:
        if re.search(pattern, body):
            out.append(f"{file_path}: {msg}")
    return out


def has_banned_phrase(body: str) -> str | None:
    lo = body.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lo:
            return phrase
    return None


def extract_one(file_path: Path, label: str, strip_code: bool) -> tuple[dict | None, list[str], str | None]:
    text = file_path.read_text()
    fm, body = strip_frontmatter(text)

    drift = detect_drift(body, file_path)

    if strip_code:
        body = strip_code_blocks(body)

    body = normalize_dashes(body).strip()

    banned = has_banned_phrase(body)
    if banned:
        return None, drift, f"banned phrase '{banned}'"

    user_prompt = derive_user_prompt(fm, file_path, label)

    example = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a hardware engineering assistant with deep knowledge of "
                    "the CONDUYT protocol and SDKs. Respond with the canonical conduyt "
                    "explanation, including code where it helps."
                ),
            },
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": body},
        ],
        "kind": f"conduyt-docs-{label}",
        "doc_source": str(file_path.relative_to(file_path.parents[3])) if len(file_path.parents) >= 4 else str(file_path),
    }
    return example, drift, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--docs-root",
        type=Path,
        default=Path("../conduyt/site/content/docs"),
        help="Root of the conduyt docs tree.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("data/raw/v3_conduyt_docs.jsonl"),
    )
    ap.add_argument(
        "--strip-code-from",
        action="append",
        default=[],
        help="Glob (relative to docs-root) where code blocks should be stripped. "
             "Adds to the default set defined in the script.",
    )
    args = ap.parse_args()

    if not args.docs_root.exists():
        print(f"docs root not found: {args.docs_root}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)

    result = ExtractionResult()

    # Build the full glob -> (label, strip_code) map, including user overrides.
    targets: list[tuple[str, str, bool]] = list(CATEGORIES)
    for extra in args.strip_code_from:
        targets.append((extra, "custom", True))

    seen_paths: set[Path] = set()
    with args.out.open("w") as fout:
        for pattern, label, strip_code in targets:
            for path in sorted(args.docs_root.glob(pattern)):
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                try:
                    example, drift, skip_reason = extract_one(path, label, strip_code)
                except Exception as e:
                    result.skipped.append(f"{path}: error: {e}")
                    continue
                if drift:
                    result.drift_warnings.extend(drift)
                if skip_reason:
                    result.skipped.append(f"{path}: skipped ({skip_reason})")
                    continue
                if example:
                    fout.write(json.dumps(example) + "\n")
                    result.examples.append(example)

    print(f"wrote {len(result.examples)} examples to {args.out}")
    if result.drift_warnings:
        print(f"\n{len(result.drift_warnings)} drift warnings (code stripping recommended for these):", file=sys.stderr)
        for w in result.drift_warnings:
            print(f"  {w}", file=sys.stderr)
    if result.skipped:
        print(f"\nskipped {len(result.skipped)} files:", file=sys.stderr)
        for s in result.skipped:
            print(f"  {s}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
