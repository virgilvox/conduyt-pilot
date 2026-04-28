# Handoff: 2026-04-27 — Phase 1 scaffold complete

## Status

Phase 1 scaffolding is complete and validated. Synthesis pipeline is wired up but **no real API calls have been made yet**. Awaiting user authorization to spend Anthropic credits on the `--limit 50` smoke run and the full `--limit 300` generation pass.

## What landed this session

### Repo structure
```
conduyt-pilot/
├── CLAUDE.md           # project rules: no Claude attribution in commits, voice rules,
│                       # research-backed verification, tracking/handoffs cadence
├── README.md           # quickstart + workflow diagram
├── pyproject.toml      # uv + python 3.11; deps: anthropic, pydantic, jsonlines, tiktoken,
│                       # pyyaml, tqdm; optional [semantic] = sentence-transformers
├── .gitignore          # ignores data/raw, data/processed, .venv, *.gguf, adapters/
├── data/
│   ├── boards/         # 8 capability JSONs (committed)
│   ├── seeds/          # 9 JSONL files, 90 examples (committed)
│   ├── raw/            # gitignored, target for synthetic outputs
│   └── processed/      # gitignored, validation/dedup/split outputs
├── prompts/
│   ├── synthesis_system.md
│   └── synthesis_template.md
├── scripts/
│   ├── 01_generate_synthetic.py
│   ├── 02_validate_dataset.py
│   ├── 03_dedupe_dataset.py
│   ├── 04_split_train_eval.py
│   └── 05_build_kaggle_dataset.py
├── kaggle/             # Phase 2 holding pen
└── tracking/
    ├── handoffs/       # this file lives here
    ├── decisions/
    └── notes/
```

### Boards (`data/boards/*.json`)

8 board capability JSONs, each with `_sources` array citing upstream variant headers / vendor docs and a `_notes` block describing non-obvious quirks. All 8 parse as JSON:

| board id | mcu | ram_kb | flash_kb | wifi | ble |
|---|---|---|---|---|---|
| esp32-s3-devkitc-1 | ESP32-S3 | 512 | 8192 | yes | yes |
| adafruit-feather-esp32-s3 | ESP32-S3 | 512 | 4096 (4MB+PSRAM, PID 5477) | yes | yes |
| raspberry-pi-pico | RP2040 | 264 | 2048 | no | no |
| raspberry-pi-pico-w | RP2040 | 264 | 2048 | yes | yes |
| arduino-uno-r4-wifi | RA4M1 | 32 | 256 | yes (via ESP32-S3 coproc) | yes |
| seeed-xiao-esp32-c3 | ESP32-C3 | 400 | 4096 | yes | yes |
| adafruit-feather-nrf52840-sense | nRF52840 | 256 | 1024 | no | yes |
| arduino-nano-33-ble | nRF52840 | 256 | 1024 | no | yes |

**Source strategy:** for boards already profiled in `../conduyt/protocol/boards/*.yml` (esp32-s3-devkitc-1, raspberry-pi-pico, arduino-uno-r4-wifi, plus partial overlap on c3 and nrf52840) the conduyt YAMLs were used as the primary citation, supplemented with vendor pages. The other 5 boards were verified via a research subagent against Adafruit Learning System, Seeed Wiki, Arduino Docs, and the upstream variant headers in `espressif/arduino-esp32`, `earlephilhower/arduino-pico`, `adafruit/Adafruit_nRF52_Arduino`, and `arduino/ArduinoCore-mbed`.

**One key correction caught during research:** the Adafruit Feather ESP32-S3 PID 5477 is the **4MB flash + 2MB PSRAM** variant, not 8MB+PSRAM. PID 5323 is the 8MB-no-PSRAM variant. The board JSON reflects the 5477 spec.

### Seeds (`data/seeds/*.jsonl`)

9 hand-curated files, exactly 10 examples each, **90 total**. All 90 pass the validator (zero violations across the schema, banned-phrase, code-fence, token-size, and duplicate checks):

| file | content focus |
|---|---|
| arduino_basics.jsonl | blink, serial, digitalRead/Write, analogRead, PWM, attachInterrupt, tone |
| arduino_i2c.jsonl | BME280, BME680, MPU6050, SHT41, SHT30, SSD1306, SH1106, BMP280, APDS9960, hysteresis-thresholding |
| arduino_spi.jsonl | SD card, ePaper SSD1680, generic SPI flash JEDEC, ST7735, ST7789, MAX6675, SSD1351, SX1262 LoRa, SPI loopback |
| arduino_neopixel.jsonl | rainbow, color-wipe, chase, theater chase, pulse, VU meter, sparkle, button-cycle, fire effect, NeoMatrix scroll |
| platformio_configs.jsonl | bare-bones, lib_deps, multi-env, OTA env, debug-vs-release, Pico SDK env, R4 BLE, Sense sensors, Nano 33 BLE, Pico W |
| conduyt_basics.jsonl | minimal serial firmware, host-side pin control, datastreams, mock transport tests, OLED via module |
| conduyt_advanced.jsonl | I2C bridges, BLE/WebSerial, MQTT, multi-module, ReconnectTransport, browser hosts, raw I2C from host |
| esp_idf_basics.jsonl | gpio, wifi STA, http_client, mqtt_client, ISR queue, adc_oneshot v5, ledc fade, i2c_master v5, NVS counter, deep sleep |
| esp_arduino_wifi.jsonl | WiFi.begin, WebServer, HTTPS POST, ArduinoOTA, AsyncMqttClient, Pico W WiFi, R4 WiFiS3 scan, SoftAP, NTP, raw TCP client |

**Voice characteristics enforced in every seed:** no em dashes, no en dashes, no emojis, no marketing-fluff openers, no "delve into" / "let's explore" / "dive into" / "harness the power" / "unleash" / "leverage". State assumptions explicitly when ambiguous.

### Prompts (`prompts/*.md`)

- `synthesis_system.md`: voice rules verbatim, code rules, response format spec, banned-phrase list, voice anchor example.
- `synthesis_template.md`: per-tuple message construction with framework-specific structure (single .ino vs. platformio.ini+main.cpp vs. ESP-IDF main.c+component note vs. .ts host vs. .ino conduyt firmware).

### Scripts

| script | role | smoke status |
|---|---|---|
| 01_generate_synthetic.py | Walk 14,550-tuple matrix; call Anthropic API; write `data/raw/synthetic_<ts>.jsonl`. Supports `--dry-run`, `--limit`, `--max-cost-usd`, `--model`, `--board-glob`, `--seed`. | dry-run verified; **API run NOT yet executed** |
| 02_validate_dataset.py | Schema, banned-phrase, code-fence, token-count (cl100k proxy), intra-file dup checks. Writes `<stem>_clean.jsonl` to `data/processed/`. | passes 90/90 seeds with zero violations |
| 03_dedupe_dataset.py | Cross-file exact dedup via normalized SHA256 of user message; optional `--semantic` flag uses sentence-transformers all-MiniLM-L6-v2. | compiles |
| 04_split_train_eval.py | 90/10 train/eval, stratified by `board_id`. | compiles |
| 05_build_kaggle_dataset.py | Bundles `processed/{train,eval}.jsonl` + `boards/*.json` + `metadata.json` into `conduyt-pilot-data-v<N>.zip`. | compiles |

### Generation matrix (informational)

`01_generate_synthetic.py` with default settings would walk 14,550 tuples:
- by framework: arduino 3300, platformio 3300, esp-idf 1350, conduyt-firmware 3300, conduyt-js 3300
- by board: ranges 1320 (Pico, no wifi/ble tasks) to 2250 (ESP32-S3 boards, full feature set)

`--limit 300` randomly samples 300 of those with seed=42, which gives reasonable board coverage by stratification.

## Phase 1 deliverables checklist

- [x] All 8 board JSONs with verified pinouts and source citations
- [x] All 9 seed JSONLs with ~10 hand-curated examples each (90 total)
- [x] Synthesis scripts with `--dry-run` working
- [ ] `--limit 50` smoke run (gated on user authorization to spend API credits)
- [ ] `--limit 300` full run -> ~390-example train+eval split
- [x] Validation report shows zero banned-phrase violations on the 90 seeds
- [ ] Kaggle dataset zip ready to upload (gated on the train/eval files existing)

## Decisions worth knowing

1. **Did not run the live `--limit 50` smoke test.** The user's CLAUDE.md rule about being cautious with hard-to-reverse / cost-bearing actions made me stop at the dry-run boundary. The script is verified to compile and to produce three full prompts in dry-run.
2. **Em dashes use ban list `[—, –]`.** `--` in code (e.g. command-line flags) is allowed; the validator only blocks the Unicode em/en dash characters.
3. **Token estimate is `len(text) // 4`**, not a real cl100k tokenizer. Good enough to flag oversized examples (>4096); replace with `tiktoken` if we want exactness later.
4. **Stratified split is by `board_id`**, not by framework. If we end up with framework imbalance after generation, we can re-run `04_split_train_eval.py` with framework stratification (5-line change).
5. **Pricing constants in `01_generate_synthetic.py`** are hard-coded for Opus 4.7 ($15/M in, $75/M out). Update if the price card changes.

## Open questions for the next session

1. Authorize the `--limit 50` smoke run? Estimated cost: $0.10–$0.20.
2. After smoke passes, authorize the full `--limit 300` run? Estimated cost: $0.50–$2.00 within the script's `--max-cost-usd 2.50` cap.
3. Once 300 examples are generated and validated, sample 10 random examples for spot-check before bundling for Kaggle.

## Next session pickup

Run the smoke pass, eyeball a few outputs, then the full pass:

```bash
export ANTHROPIC_API_KEY=...
uv sync
uv run scripts/01_generate_synthetic.py --limit 50  --max-cost-usd 0.50
uv run scripts/02_validate_dataset.py data/raw/synthetic_*.jsonl

# Spot-check 10 random
shuf -n 10 data/raw/synthetic_*.jsonl

# If clean, full run:
uv run scripts/01_generate_synthetic.py --limit 300 --max-cost-usd 2.50
uv run scripts/02_validate_dataset.py data/raw/synthetic_*.jsonl
cat data/processed/*_clean.jsonl > data/processed/all.jsonl
uv run scripts/03_dedupe_dataset.py data/processed/all.jsonl --out data/processed/dedup.jsonl
uv run scripts/04_split_train_eval.py data/processed/dedup.jsonl
uv run scripts/05_build_kaggle_dataset.py
```

Then upload the zip to Kaggle as a private Dataset, and Phase 1 is closed.
