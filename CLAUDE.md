# conduyt-pilot Project Rules

## Mission

Phase 1 of the conduyt fine-tune pilot: build a clean training dataset for a small embedded-coding model. The dataset is committed seeds + synthesized examples + verified board capability JSONs. Phase 2 is Kaggle training.

## Authoritative source for board data

The neighboring repo at `../conduyt/` is the source of truth for board capabilities and protocol details.

- `../conduyt/protocol/boards/*.yml`: per-board YAML profiles with verified pin caps, MCU id, I2C/SPI/UART buses, and pin role assignments. Source-cite the upstream pin headers in each YAML's top comment block.
- `../conduyt/protocol/board-profiles.json`: compiled JSON view of all MCUs and boards (generated from the YAMLs).
- `../conduyt/firmware/examples/*.ino`: canonical Conduyt firmware examples. Use these for the Conduyt voice/style in seeds.
- `../conduyt/sdk/js/README.md` and `../conduyt/sdk/js/src/`: `conduyt-js` host API surface. Use for `conduyt-js` framework examples.

**Never edit anything inside `../conduyt/`.** Read-only reference. All work happens inside `conduyt-pilot/`.

When a board the user requested is not in `../conduyt/protocol/boards/`, do web research and cite sources at the top of the resulting JSON. PlatformIO and the upstream variant headers (espressif/arduino-esp32, earlephilhower/arduino-pico, ArduinoCore-renesas, Adafruit_nRF52_Arduino) are the trustworthy sources for pin maps. Vendor product pages are good for RAM/flash sizes and special peripherals.

## Voice & content rules (apply to all generated code, examples, prompts, docs)

- No em dashes, no double-dashes, no en dashes used as em dashes.
- No emojis anywhere. Not in code, comments, prompts, or docs.
- No "it's not just X, it's Y" framings.
- No marketing-fluff openers ("In today's fast-paced world…").
- No "delve into", "let's explore", "dive deep", "in this article", "unleash", "leverage" as a verb.
- Direct, technical, mildly punk tone. Short sentences over long ones.
- Code blocks always include the necessary `#include` lines and explicit pin definitions.
- State assumptions explicitly when the task is ambiguous (e.g. "Assuming SDA=GPIO8, SCL=GPIO9 per the board profile").
- Prefer PlatformIO conventions when applicable.
- For CONDUYT examples, follow the patterns in `../conduyt/firmware/examples/` and `../conduyt/sdk/js/`.

## Engineering rules

### Never give Claude credit
- **No `Co-Authored-By: Claude` trailers in commits. Ever.**
- No `Generated with Claude Code` lines in PR bodies.
- No author attribution to Claude, Anthropic, or any AI in any committed artifact (code comments, README, generated examples, dataset metadata).
- The user is the sole author. If a future helper script auto-injects an attribution line, strip it.

### Smart and cautious; separation of concerns
- Each script in `scripts/` does one thing and writes a typed output file. Validation lives in `02_validate_dataset.py`, not inside the generator.
- Don't mix prompts, code, and data in the same file. Prompts in `prompts/`, code in `scripts/`, data in `data/`.
- Don't reach across phase boundaries. Phase 2 (Kaggle/training) lives in `kaggle/` and is gated on Phase 1 sign-off.
- Don't edit `data/seeds/` from a script. Seeds are hand-curated and committed.
- Don't add features beyond the spec. If the spec says `--dry-run` and `--limit`, don't add `--retry-from-checkpoint`. Ask first.

### Research-backed; double-check before writing
- Before writing a board JSON, verify pin maps against the upstream variant header (cite path/URL in a top comment in the JSON file).
- Before writing an Arduino example, search for the canonical version (Adafruit example sketches, ArduinoGetStarted, Pololu, Sparkfun docs). Don't invent register-level code from memory.
- For library-name and version pinning in `platformio.ini`, verify the registry name (`pio pkg search`). Don't guess.
- If you can't find a verified source for a fact, say "I couldn't verify X" rather than write it down.

### Tracking
- All work-in-progress notes, decisions, and handoffs live in `tracking/`.
  - `tracking/handoffs/YYYY-MM-DD_<short-slug>.md`: written at the end of each big working session.
  - `tracking/decisions/NNNN_<slug>.md`: short ADR-style notes for non-obvious calls.
  - `tracking/notes/`: scratch research notes, source citations gathered during a task.
- A handoff covers: what changed, what's verified vs unverified, open questions, exactly what the next session should pick up.
- Don't pile fresh notes into an old handoff. New session = new file.

### Commits
- Conventional-commit-ish prefix when it fits: `feat:`, `fix:`, `data:`, `docs:`, `chore:`. Otherwise plain imperative.
- One logical change per commit. Don't bundle "add 8 board JSONs + scaffold scripts + write validator" into a single commit.
- Never commit secrets. `ANTHROPIC_API_KEY` lives in env, never in a config file.
- Never commit `data/raw/` or `data/processed/` (gitignored). Only `data/seeds/` and `data/boards/` are tracked.

## Directory map

```
conduyt-pilot/
├── CLAUDE.md                # this file
├── README.md
├── pyproject.toml           # uv-managed, python 3.11
├── .gitignore
├── data/
│   ├── seeds/               # COMMITTED hand-curated examples
│   ├── raw/                 # gitignored synthetic outputs
│   ├── processed/           # gitignored cleaned/validated/split outputs
│   └── boards/              # COMMITTED board capability JSONs
├── prompts/
│   ├── synthesis_system.md
│   └── synthesis_template.md
├── scripts/
│   ├── 01_generate_synthetic.py
│   ├── 02_validate_dataset.py
│   ├── 03_dedupe_dataset.py
│   ├── 04_split_train_eval.py
│   └── 05_build_kaggle_dataset.py
├── kaggle/                  # Phase 2; keep empty for now
└── tracking/
    ├── handoffs/
    ├── decisions/
    └── notes/
```

## Phase gate

Don't proceed past Phase 1 without showing the user:
1. The validation report from `02_validate_dataset.py`.
2. A random sample of 10 generated examples for spot-check.
3. The final `data/processed/train.jsonl` and `eval.jsonl` line counts.
