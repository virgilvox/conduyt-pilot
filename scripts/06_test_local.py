#!/usr/bin/env python3
"""Local sanity test of a fine-tuned GGUF.

Pulls the GGUF from a Hugging Face repo, runs the same 5 hardcoded probes used
in train.ipynb plus 10 sampled prompts from data/processed/eval.jsonl, and
prints a side-by-side base-vs-finetune comparison so you can eyeball whether
the fine-tune is shifting outputs.

Usage:
  uv run scripts/06_test_local.py
  uv run scripts/06_test_local.py --finetune-repo virgilvox/conduyt-pilot-1.5b-gguf
  uv run scripts/06_test_local.py --quant Q5_K_M
  uv run scripts/06_test_local.py --skip-base   # only run finetune
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import textwrap
from pathlib import Path

try:
    from llama_cpp import Llama
except ImportError:
    print(
        "llama-cpp-python is not installed. Install it with:\n"
        "  pip install llama-cpp-python==0.3.21\n"
        "(or with --extra-index-url for prebuilt CPU/CUDA wheels)",
        file=sys.stderr,
    )
    raise


PROBES: list[str] = [
    "Blink an LED on the ESP32-S3 DevKitC-1 onboard NeoPixel at 1 Hz.",
    "Read a BME280 over I2C and print T, P, H every 2 seconds. Target board: Adafruit Feather nRF52840 Sense.",
    "Write a platformio.ini for an Adafruit Feather nRF52840 Sense project that uses Adafruit_LSM6DS and Adafruit_BMP280.",
    "Conduyt firmware sketch on a Pico that exposes a writable angle datastream driving a servo on GP15.",
    "On an ESP32-S3, connect to WiFi and POST the millis() value as JSON to https://example.com/log every 30 seconds.",
]


def load_eval_prompts(path: Path, n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    rows: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rng.shuffle(rows)
    return [r["messages"][1]["content"] for r in rows[:n]]


def make_llm(repo_id: str, filename_pattern: str, n_ctx: int) -> Llama:
    return Llama.from_pretrained(
        repo_id      = repo_id,
        filename     = filename_pattern,
        n_ctx        = n_ctx,
        n_gpu_layers = 0,
        verbose      = False,
    )


def run_chat(llm: Llama, prompt: str, max_tokens: int) -> str:
    resp = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": "You are a hardware engineering assistant. Respond with working code and a brief explanation."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    return resp["choices"][0]["message"]["content"]


def trunc(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    return text[:n] + "..."


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--finetune-repo", default="virgilvox/conduyt-pilot-1.5b-gguf")
    ap.add_argument("--base-repo",     default="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF")
    ap.add_argument(
        "--quant",
        default="Q4_K_M",
        help="GGUF quantization label; matched against the filename via *<quant>*",
    )
    ap.add_argument("--n-ctx",       type=int, default=4096)
    ap.add_argument("--max-tokens",  type=int, default=400)
    ap.add_argument("--n-eval",      type=int, default=10)
    ap.add_argument("--seed",        type=int, default=3407)
    ap.add_argument("--skip-base",   action="store_true")
    ap.add_argument(
        "--eval-jsonl",
        type=Path,
        default=Path("data/processed/eval.jsonl"),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("tracking/notes/local_eval_results.md"),
    )
    args = ap.parse_args()

    pattern = f"*{args.quant}*.gguf"

    print(f"loading finetune {args.finetune_repo} ({pattern})")
    ft = make_llm(args.finetune_repo, pattern, args.n_ctx)

    if not args.skip_base:
        print(f"loading base     {args.base_repo} ({pattern})")
        base = make_llm(args.base_repo, pattern, args.n_ctx)
    else:
        base = None

    eval_prompts: list[str] = []
    if args.eval_jsonl.exists():
        eval_prompts = load_eval_prompts(args.eval_jsonl, args.n_eval, args.seed)
    else:
        print(f"warning: {args.eval_jsonl} not found, skipping eval probes")

    all_prompts = [("probe", p) for p in PROBES] + [("eval", p) for p in eval_prompts]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as fout:
        fout.write(f"# Local eval results\n\n")
        fout.write(f"- finetune: `{args.finetune_repo}` ({args.quant})\n")
        fout.write(f"- base:     `{args.base_repo}` ({args.quant})\n")
        fout.write(f"- eval probes: {len(eval_prompts)}\n\n")

        for kind, prompt in all_prompts:
            print(f"\n--- {kind}: {trunc(prompt, 80)} ---")
            ft_out = run_chat(ft, prompt, args.max_tokens)
            base_out = run_chat(base, prompt, args.max_tokens) if base else "(skipped)"

            print(f"\n  [base]:")
            print(textwrap.indent(trunc(base_out, 600), "    "))
            print(f"\n  [finetune]:")
            print(textwrap.indent(trunc(ft_out, 600), "    "))

            fout.write(f"## {kind}: {prompt}\n\n")
            fout.write(f"### base\n```\n{base_out}\n```\n\n")
            fout.write(f"### finetune\n```\n{ft_out}\n```\n\n---\n\n")

    print(f"\nfull report -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
