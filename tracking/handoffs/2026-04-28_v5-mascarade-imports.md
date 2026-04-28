# 2026-04-28 v5 corpus: mascarade imports

## Why

User asked whether the upstream `electron-rare/mascarade` finetune
datasets could supplement our corpus. After fetching, format-converting,
and ASCII-sanitizing, 23 hand-curated examples from 4 of the 10 builder
scripts add coverage we did not have:

- Bare-metal ARM Cortex-M4 startup assembly with vector table
- RISC-V bare-metal LED blink (HiFive1)
- STM32F4 LL drivers DMA + ADC
- Raspberry Pi bare-metal C GPIO
- Teensy 4.1 i.MX RT1062 startup
- ESP-IDF MQTT client with TLS + auto-reconnect
- Home Assistant YAML auto-discovery
- FreeRTOS architecture across WiFi + MQTT + deep sleep
- PlatformIO captive-portal WiFi manager + MQTT + deep sleep
- Native + embedded unit tests with Unity framework
- ESP32 BLE scanner to MQTT bridge
- Custom PlatformIO board.json definitions
- ESPAsyncWebServer REST API for GPIO/ADC
- PlatformIO CI/CD with GitHub Actions
- Modular sensor abstraction PIO library
- Synchronous buck converter design (12 V to 3.3 V)
- BLDC FOC with Clarke and Park transforms in C
- MOSFET selection for half-bridge gate driver with thermal calc
- CC-CV LiPo charger from a buck converter

These extend the model into bare-metal embedded, advanced motor
control, and the production PlatformIO + HA toolchain. Topics our
v3/v4 corpus only brushed against.

## Process

1. Cloned mascarade shallow.
2. Ran the four relevant builders in seeds-only mode (`--with-hf` NOT
   enabled to avoid diluting v3 contrast signal with uncurated
   StackExchange content).
3. Format-converted ShareGPT (`{conversations: [{from, value}]}`) to
   our OpenAI schema (`{messages: [{role, content}]}`).
4. ASCII-sanitized: em-dashes, en-dashes, micro signs, multiplication
   signs, arrows, smart quotes, approx-equal, etc. mapped to ASCII.
   Degree signs handled with unit-aware substitution (`100 degC` ->
   `100 C`, etc.) to avoid double-spaces. Box-drawing and Greek
   letters left intact.
5. Tagged each example with `kind: "mascarade-<bucket>"`, plus
   `source`, `license`, and `license_holder` metadata for
   traceability.
6. Validated against our voice rules: 23 of 23 pass clean.
7. Combined with v1+v2+v3+v4 clean files, dedup found 1 duplicate
   across the full corpus.
8. Stratified split 90/10.

## Final dataset (v5)

```
train: 453 examples
eval:  49 examples
total: 502

stratification by board (mascarade examples are untagged, so they
distribute through the untagged pool alongside our generic v3/v4
classifiers):

  adafruit-feather-esp32-s3:        17
  adafruit-feather-nrf52840-sense:  14
  arduino-nano-33-ble:              12
  arduino-uno-r4-wifi:              82
  esp32-s3-devkitc-1:              123
  raspberry-pi-pico:                61
  raspberry-pi-pico-w:              10
  seeed-xiao-esp32-c3:              12
  (untagged: ~171, includes 23 mascarade imports + v3 disambiguation
   + v4 fundamentals/protocols/components)
```

Bundle: `conduyt-pilot-data-v5.zip` = 215 KB.

## Attribution

Upstream copyright and license preserved per MIT terms in
`THIRD_PARTY.md` at repo root. Each imported example also carries
inline `source` and `license` fields in the JSONL record.

## Trajectory

| Version | Train | Eval | Total | Notes |
|---|---|---|---|---|
| v2 | 243 | 25 | 268 | 92+ conduyt-js examples added; still mashed Arduino into JS |
| v3 | 329 | 35 | 364 | +96 contrast (Arduino vs conduyt-js) |
| v4 | 432 | 47 | 479 | +115 hardware/electronics breadth |
| v5 | 453 | 49 | 502 | +23 mascarade imports (bare-metal, FOC, FreeRTOS depth) |

## Open items

- v5 bundle upload to Kaggle when user is ready to run the next
  fine-tune.
- Eval prompts (in addition to v3/v4 ones):
  - "Write bare-metal ARM Cortex-M4 startup with a vector table." (tests
    mascarade embedded depth)
  - "Design a buck converter from 12 V to 3.3 V at 2 A." (tests
    mascarade power)
  - "Write a custom PlatformIO board definition for an ESP32-S3 PCB."
    (tests mascarade platformio)
  - All v3 contrast prompts must still produce clean conduyt-js without
    sliding into Arduino C++ - the imports are framework-neutral and
    should not regress this.

