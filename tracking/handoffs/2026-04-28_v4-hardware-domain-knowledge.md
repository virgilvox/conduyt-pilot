# 2026-04-28 v4 corpus: hardware and electronics domain knowledge

## Why

v3 fixed the framework boundary (Arduino C++ vs conduyt-js JavaScript).
What it did not fix: the model still has thin domain knowledge about
hardware itself. It does not know "what NTC resistor with what divider
for a thermistor", or "what pull-up sizing for I2C", or "why my I2C scan
returns nothing". A model that can write valid conduyt-js but cannot
answer "which MOSFET for switching a 12 V solenoid from 3.3 V GPIO" is
half a tool.

v4 fills the breadth gap with 115 hand-curated examples covering
electronics fundamentals, component selection, circuit recipes,
protocol pitfalls, sensor wiring + code, actuator drive, power
management, debugging walkthroughs, end-to-end project archetypes, and
per-board hardware facts.

## What changed

Ten new seed files in `data/seeds/`:

| File | Count | Anchor |
|------|-------|--------|
| `v4_electronics_fundamentals.jsonl` | 18 | Ohm's law, divider math, RC, debounce, decoupling, ESR, ground loops |
| `v4_component_selection.jsonl`      | 12 | Sensor / driver / regulator picks with part numbers and tradeoffs |
| `v4_circuit_patterns.jsonl`         | 12 | MOSFET switching, level shifters, flyback, INA219 sense, ESD, charger |
| `v4_protocols_deep.jsonl`           | 10 | I2C / SPI / UART / 1-Wire / CAN / RS485 / WS2812 / MQTT / BLE GATT pitfalls |
| `v4_sensors_deep.jsonl`             | 15 | Thermistor + Steinhart, BME280 reg map, MPU6050 yaw drift, INA219, VL53L0X, DS18B20, HX711, HMC5883L cal, soil moisture, gas, gesture, UV, SCD41 |
| `v4_actuators_deep.jsonl`           | 10 | Servo PWM, A4988 Vref, BLDC ESC, solenoid + flyback, relays, NeoPixel power, BLDC, vibration, heater PID, buzzer |
| `v4_power_management.jsonl`         | 10 | LDO vs buck, heat dissipation, current budgeting, ESP32 deep sleep, 18650 + BMS, SoC table, solar harvest, USB-PD, CR2032 life, brownout |
| `v4_debug_diagnostics.jsonl`        | 10 | Ranked diagnostic walkthroughs for I2C silent, WiFi drop, ADC noise, BLE iOS pairing, PWM jitter, servo jitter, stepper skip, sensor wrong values, brownout, USB drops |
| `v4_project_archetypes.jsonl`       | 6  | Battery temp logger, plant monitor, smart switch, CO2 alert, bike speedometer, autonomous robot |
| `v4_board_specific_facts.jsonl`     | 12 | Per-board ADC bits, GPIO sink limits, special peripherals, gotchas (ADC2 + WiFi, USB on GPIO 19/20, etc.) |

Three new system prompts anchor v4:

1. `SYS_HARDWARE`: "Hardware engineering and embedded systems advisor.
   Specific component values, part numbers, code where relevant."
2. `SYS_DEBUG`: "Debugging assistant. Ranked-most-likely-first causes,
   concrete diagnostic steps, exact register or code path."
3. `SYS_PROJECT`: "End-to-end project designer. Parts list, wiring,
   firmware outline, top three pitfalls."

## Validation

```
v4_electronics_fundamentals.jsonl: 18 / 18 kept
v4_component_selection.jsonl:      12 / 12 kept
v4_circuit_patterns.jsonl:         12 / 12 kept
v4_protocols_deep.jsonl:           10 / 10 kept
v4_sensors_deep.jsonl:             15 / 15 kept
v4_actuators_deep.jsonl:           10 / 10 kept
v4_power_management.jsonl:         10 / 10 kept
v4_debug_diagnostics.jsonl:        10 / 10 kept
v4_project_archetypes.jsonl:        6 /  6 kept
v4_board_specific_facts.jsonl:     12 / 12 kept
total: 115 / 115, 0 dropped, 0 violations
```

## Final dataset (v4)

```
train: 432 examples
eval:  47 examples
total: 479

stratification:
  adafruit-feather-esp32-s3:        17
  adafruit-feather-nrf52840-sense:  14
  arduino-nano-33-ble:              12
  arduino-uno-r4-wifi:              82
  esp32-s3-devkitc-1:              123
  raspberry-pi-pico:                61
  raspberry-pi-pico-w:              10
  seeed-xiao-esp32-c3:              12
  (untagged: 148, mostly v4 fundamentals/protocols/components which are
  not board-specific, plus v3 disambiguation classifiers)
```

The untagged share went up because most v4 hardware fundamentals are
generic (Ohm's law does not need a board_id). The split function
distributes untagged into train/eval at the same 90/10 ratio.

Bundle: `conduyt-pilot-data-v4.zip` = 180 KB.

## Trajectory across versions

| Version | Train | Eval | Notes |
|---|---|---|---|
| v1 | 90 + synthesis | 0 | Initial seeds + synthetic. Model produced JS hallucinations. |
| v2 | 243 | 25 | Added 92+ conduyt-js examples. Still mashed Arduino into JS. |
| v3 | 329 | 35 | Added 96 contrastive examples (Arduino vs conduyt-js boundary). |
| v4 | 432 | 47 | Added 115 hardware domain examples. Total +160 over v2 baseline. |

## Open items

- v4 bundle upload to Kaggle.
- v4 fine-tune run with `kaggle/train.ipynb` (existing hyperparameters
  r=32, alpha=64, dropout=0; consider 6 epochs for v4 since the corpus
  is bigger; eval prompts will tell us if it overfits).
- MLC export with `kaggle/convert_mlc.ipynb` (cpu wheels, already
  debugged in prior session).
- WebLLM smoke test once MLC artifacts land. Eval prompts to check:
  - "Drive a 12 V solenoid from a 3.3 V Pico, give me the circuit and
    code." (tests v4 component_selection + circuit_patterns)
  - "I have a 5 V button signal that needs to talk to a 3.3 V ESP32.
    What do I do?" (tests v4 fundamentals)
  - "Blink an LED. Show both the Arduino sketch and the conduyt-js
    host code." (tests v3 contrast)
  - "My I2C scan returns nothing on an ESP32-S3. What do I check?"
    (tests v4 debug_diagnostics)

## End-to-end automation pre-flight

Same as v3 handoff. The user provides `kaggle.json` and an HF write
token; the assistant pushes dataset + kernel, monitors with periodic
status polling, pulls outputs, uploads to HF. Quality is data-bound;
the pipeline runs end-to-end and produces loadable artifacts.

## Hygiene check on this commit

Grep of seed files and handoff for "Claude" / "Anthropic": NONE.
Grep of commit message body before sending: NONE.
