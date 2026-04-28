#!/usr/bin/env python3
"""Generate synthetic embedded-coding training examples.

Walks the matrix of (board x peripheral x task x framework) tuples, skipping
combinations that don't make sense (e.g. WiFi on a board without a radio), and
calls the Anthropic API to synthesize one example per tuple per the prompts in
prompts/.

Outputs one example per line to data/raw/synthetic_<timestamp>.jsonl.

Flags:
  --dry-run            Print the first 3 prompts that would be sent and exit.
  --limit N            Cap total API calls to N tuples.
  --max-cost-usd X     Stop when projected total cost exceeds X. (Conservative
                       estimate based on token counts and the published Opus 4.7
                       price card.)
  --model MODEL        Override the synthesis model. Default: claude-opus-4-7.
  --board-glob G       Restrict to boards matching G (e.g. "esp32-s3-*").

Env: ANTHROPIC_API_KEY required for non-dry-run.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# anthropic SDK is only required for actual API calls; dry-run works without it.
try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore


# Pricing (USD per million tokens) for Claude Opus 4.7. Update if the card changes.
PRICE_INPUT_PER_M = 15.0
PRICE_OUTPUT_PER_M = 75.0

# Conservative output guess per example (used for budget planning before the call
# completes); actual cost is logged from the response.usage payload.
ASSUMED_OUTPUT_TOKENS = 700


PERIPHERALS: list[dict] = [
    {"name": "BME280",          "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "BME680 (BSEC2)",  "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "MPU6050",         "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "SHT41",           "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "SHT30",           "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "BMP280",          "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "VEML7700 lux",    "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "TMP117",          "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "SCD41 CO2",       "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "ADXL345",         "kind": "i2c-sensor",   "needs": ["i2c"]},
    {"name": "SSD1306 OLED",    "kind": "i2c-display",  "needs": ["i2c"]},
    {"name": "SH1106 OLED",     "kind": "i2c-display",  "needs": ["i2c"]},
    {"name": "ST7735 TFT",      "kind": "spi-display",  "needs": ["spi"]},
    {"name": "ST7789 TFT",      "kind": "spi-display",  "needs": ["spi"]},
    {"name": "SSD1351 RGB OLED","kind": "spi-display",  "needs": ["spi"]},
    {"name": "SSD1680 ePaper",  "kind": "spi-display",  "needs": ["spi"]},
    {"name": "SD card",         "kind": "spi-storage",  "needs": ["spi"]},
    {"name": "MAX6675 thermo",  "kind": "spi-sensor",   "needs": ["spi"]},
    {"name": "W25Q SPI flash",  "kind": "spi-storage",  "needs": ["spi"]},
    {"name": "SX1262 LoRa",     "kind": "spi-radio",    "needs": ["spi"]},
    {"name": "WS2812 NeoPixel", "kind": "led",          "needs": ["digital_out"]},
    {"name": "Hobby servo",     "kind": "actuator",     "needs": ["pwm"]},
    {"name": "DC motor (PWM)",  "kind": "actuator",     "needs": ["pwm"]},
    {"name": "28BYJ-48 stepper","kind": "actuator",     "needs": ["digital_out"]},
    {"name": "Push button",     "kind": "input",        "needs": ["digital_in"]},
    {"name": "Rotary encoder",  "kind": "input",        "needs": ["digital_in", "interrupt"]},
    {"name": "Photo-resistor",  "kind": "analog-sensor","needs": ["analog_in"]},
    {"name": "10k pot",         "kind": "analog-sensor","needs": ["analog_in"]},
    {"name": "Piezo buzzer",    "kind": "actuator",     "needs": ["pwm"]},
    {"name": "Reed switch",     "kind": "input",        "needs": ["digital_in"]},
]

TASKS: list[dict] = [
    {"name": "read once",                   "verb": "read once and print"},
    {"name": "read every Ns",               "verb": "read every N seconds and print"},
    {"name": "threshold-publish-mqtt",      "verb": "publish to MQTT when value crosses a threshold", "needs": ["wifi"]},
    {"name": "threshold-publish-conduyt",   "verb": "expose as a CONDUYT datastream and push when threshold crosses"},
    {"name": "log-to-sd",                   "verb": "log readings to SD card with timestamp", "needs": ["spi"]},
    {"name": "display-on-oled",             "verb": "show the value on a 128x64 OLED"},
    {"name": "moving-average",              "verb": "compute a moving average over the last 16 samples and print"},
    {"name": "edge-only-print",             "verb": "only print when the value changes meaningfully"},
    {"name": "input-edge-action",           "verb": "trigger an output action on input edge"},
    {"name": "calibration-routine",         "verb": "run a one-time calibration at startup, then run normally"},
    {"name": "ble-broadcast",               "verb": "broadcast the value over BLE", "needs": ["ble"]},
    {"name": "websocket-stream",            "verb": "stream readings over a WebSocket", "needs": ["wifi"]},
    {"name": "sleep-between-reads",         "verb": "deep-sleep between reads to save power"},
    {"name": "fade-output",                 "verb": "fade an output PWM proportional to the reading", "needs": ["pwm"]},
    {"name": "json-http-post",              "verb": "POST a JSON body to a server when the reading changes", "needs": ["wifi"]},
]

FRAMEWORKS = ["arduino", "platformio", "esp-idf", "conduyt-firmware", "conduyt-js"]


@dataclass(frozen=True)
class Tuple4:
    board_id: str
    framework: str
    peripheral: str
    task_name: str

    def slug(self) -> str:
        return f"{self.board_id}|{self.framework}|{self.peripheral}|{self.task_name}"


def board_supports(board: dict, needs: list[str]) -> bool:
    """Coarse capability check. Avoids absurd combos."""
    if "wifi" in needs and not board.get("wifi"):
        return False
    if "ble" in needs and not board.get("ble"):
        return False
    # I2C / SPI / PWM / digital are present on every board in the corpus by virtue
    # of having defaults; we keep the check liberal here.
    return True


def framework_compatible(board: dict, framework: str) -> bool:
    mcu = board.get("mcu", "")
    if framework == "esp-idf":
        return mcu.startswith("ESP32")
    if framework == "platformio":
        return True
    if framework == "arduino":
        return True
    if framework.startswith("conduyt"):
        return True
    return True


def board_json_minimal(board: dict) -> dict:
    """Strip private metadata before inlining into a system prompt."""
    return {k: v for k, v in board.items() if not k.startswith("_")}


def render_user_message(peripheral: dict, task: dict, framework: str) -> str:
    """Generate a natural-sounding hardware request for the assistant."""
    if framework == "platformio":
        return (
            f"Write a platformio.ini and a sketch that {task['verb']} from a "
            f"{peripheral['name']}."
        )
    if framework == "conduyt-js":
        return (
            f"From a Node host using conduyt-js, {task['verb']} from a "
            f"{peripheral['name']} on the device."
        )
    if framework == "conduyt-firmware":
        return (
            f"Conduyt firmware sketch that wires a {peripheral['name']} into a "
            f"datastream and {task['verb']}."
        )
    if framework == "esp-idf":
        return (
            f"ESP-IDF v5 example: {task['verb']} from a {peripheral['name']}."
        )
    return f"Sketch that {task['verb']} from a {peripheral['name']}."


def build_system_message(framework: str, board_min: dict) -> str:
    board_block = json.dumps(board_min, indent=2)
    if framework == "conduyt-js":
        return (
            "You are a hardware engineering assistant for conduyt-js (host-side "
            "TypeScript SDK that talks to a CONDUYT firmware running on the "
            "device). Target device firmware runs on this board:\n"
            f"```json\n{board_block}\n```\n"
            "Respond with TypeScript or JavaScript host-side code."
        )
    return (
        "You are a hardware engineering assistant. Target board:\n"
        f"```json\n{board_block}\n```\n"
        "Respond with working code and a brief explanation."
    )


def all_tuples(boards: list[dict]) -> Iterator[Tuple4]:
    for board in boards:
        for framework in FRAMEWORKS:
            if not framework_compatible(board, framework):
                continue
            for peripheral in PERIPHERALS:
                if not board_supports(board, peripheral.get("needs", [])):
                    continue
                for task in TASKS:
                    needs = task.get("needs", [])
                    if not board_supports(board, needs):
                        continue
                    if "spi" in needs and peripheral["kind"].startswith("i2c"):
                        # don't ask "log to SD" with an I2C-only peripheral kind
                        # in a way that's ambiguous; this filter is a soft skip.
                        pass
                    yield Tuple4(
                        board_id=board["id"],
                        framework=framework,
                        peripheral=peripheral["name"],
                        task_name=task["name"],
                    )


def load_boards(boards_dir: Path) -> list[dict]:
    boards: list[dict] = []
    for p in sorted(boards_dir.glob("*.json")):
        with p.open() as f:
            boards.append(json.load(f))
    return boards


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000) * PRICE_INPUT_PER_M + (
        output_tokens / 1_000_000
    ) * PRICE_OUTPUT_PER_M


def synthesize_one(
    client: "anthropic.Anthropic",
    model: str,
    system_prompt: str,
    user_message: str,
    synthesis_system_md: str,
    synthesis_template_md: str,
    board_min: dict,
    framework: str,
    peripheral: str,
    task_verb: str,
) -> tuple[dict | None, dict]:
    """Call the synthesis model. Returns (parsed_example, usage_dict)."""

    template_filled = (
        synthesis_template_md
        + "\n\n---\n\n"
        + f"**Board name:** {board_min.get('name', board_min.get('id'))}\n"
        + f"**Framework:** {framework}\n"
        + f"**Peripheral / focus:** {peripheral}\n"
        + f"**Task type:** {task_verb}\n\n"
        + f"**Board capability JSON (inline this):**\n```json\n{json.dumps(board_min, indent=2)}\n```\n\n"
        + f"The user message MUST be: \"{user_message}\"\n"
        + "Output ONLY the JSON object."
    )

    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        system=synthesis_system_md,
        messages=[{"role": "user", "content": template_filled}],
    )

    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    # Strip markdown fences if the model added them.
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None, {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
    obj["board_id"] = board_min["id"]
    return obj, {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-cost-usd", type=float, default=2.5)
    ap.add_argument("--model", default="claude-opus-4-7")
    ap.add_argument("--board-glob", default="*")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--boards-dir", type=Path, default=Path("data/boards"))
    ap.add_argument("--prompts-dir", type=Path, default=Path("prompts"))
    ap.add_argument("--out-dir", type=Path, default=Path("data/raw"))
    args = ap.parse_args()

    boards = [
        b for b in load_boards(args.boards_dir)
        if Path(b["id"]).match(args.board_glob)
    ]
    if not boards:
        print(f"no boards matched {args.board_glob}", file=sys.stderr)
        return 1

    synthesis_system_md = (args.prompts_dir / "synthesis_system.md").read_text()
    synthesis_template_md = (args.prompts_dir / "synthesis_template.md").read_text()

    tuples = list(all_tuples(boards))
    rng = random.Random(args.seed)
    rng.shuffle(tuples)
    if args.limit is not None:
        tuples = tuples[: args.limit]

    print(f"matrix size: {len(tuples)} tuples")
    print(f"boards:      {len(boards)}")
    print(f"frameworks:  {FRAMEWORKS}")
    print(f"model:       {args.model}")
    print(f"budget cap:  ${args.max_cost_usd:.2f}")
    print()

    if args.dry_run:
        for tup in tuples[:3]:
            board = next(b for b in boards if b["id"] == tup.board_id)
            board_min = board_json_minimal(board)
            peripheral = next(p for p in PERIPHERALS if p["name"] == tup.peripheral)
            task = next(t for t in TASKS if t["name"] == tup.task_name)
            print("=" * 60)
            print(f"TUPLE: {tup.slug()}")
            print(f"\nSYSTEM:\n{build_system_message(tup.framework, board_min)}")
            print(f"\nUSER:\n{render_user_message(peripheral, task, tup.framework)}")
            print()
        return 0

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2
    if anthropic is None:
        print("anthropic SDK not installed; run `uv sync`", file=sys.stderr)
        return 2

    client = anthropic.Anthropic(api_key=api_key)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out_dir / f"synthetic_{ts}.jsonl"

    total_in = 0
    total_out = 0
    written = 0
    failed = 0

    print(f"writing -> {out_path}\n")

    with out_path.open("w") as fout:
        for i, tup in enumerate(tuples, 1):
            board = next(b for b in boards if b["id"] == tup.board_id)
            board_min = board_json_minimal(board)
            peripheral = next(p for p in PERIPHERALS if p["name"] == tup.peripheral)
            task = next(t for t in TASKS if t["name"] == tup.task_name)

            user_message = render_user_message(peripheral, task, tup.framework)

            try:
                obj, usage = synthesize_one(
                    client=client,
                    model=args.model,
                    system_prompt=synthesis_system_md,
                    user_message=user_message,
                    synthesis_system_md=synthesis_system_md,
                    synthesis_template_md=synthesis_template_md,
                    board_min=board_min,
                    framework=tup.framework,
                    peripheral=peripheral["name"],
                    task_verb=task["verb"],
                )
            except Exception as e:
                print(f"  [{i}/{len(tuples)}] {tup.slug()} ERROR: {e}", file=sys.stderr)
                failed += 1
                continue

            total_in += usage["input_tokens"]
            total_out += usage["output_tokens"]

            running_cost = estimate_cost(total_in, total_out)
            if obj is not None:
                fout.write(json.dumps(obj) + "\n")
                fout.flush()
                written += 1
                print(
                    f"  [{i}/{len(tuples)}] {tup.slug()}  "
                    f"in={usage['input_tokens']} out={usage['output_tokens']} "
                    f"cum=${running_cost:.4f}"
                )
            else:
                failed += 1
                print(f"  [{i}/{len(tuples)}] {tup.slug()} JSON_PARSE_FAIL", file=sys.stderr)

            if running_cost > args.max_cost_usd:
                print(
                    f"\nbudget cap ${args.max_cost_usd:.2f} reached at "
                    f"${running_cost:.4f}; stopping",
                    file=sys.stderr,
                )
                break

    print()
    print(f"written:    {written}")
    print(f"failed:     {failed}")
    print(f"in tokens:  {total_in}")
    print(f"out tokens: {total_out}")
    print(f"est cost:   ${estimate_cost(total_in, total_out):.4f}")
    print(f"output:     {out_path}")
    return 0 if written > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
