# Synthesis user-message template

Use this template when calling the synthesis model. Fill in the placeholders. The board capability JSON is the literal contents of `data/boards/<board_id>.json` (excluding the leading `_sources` and `_notes` fields, which are for human consumption only).

---

Generate ONE training example for the following spec.

**Board:** {board_name}
**Framework:** {framework}  (one of: arduino, platformio, esp-idf, conduyt-js, conduyt-firmware)
**Peripheral / focus:** {peripheral}
**Task type:** {task_type}

**Board capability JSON** (inline this verbatim into the assistant's `system` message):
```json
{board_json_minimal}
```

**System message format:**
For frameworks `arduino`, `platformio`, `conduyt-firmware`, `esp-idf`, use:
> You are a hardware engineering assistant. Target board:
> ```json
> {board_json_minimal}
> ```
> Respond with working code and a brief explanation.

For framework `conduyt-js`, use:
> You are a hardware engineering assistant for conduyt-js (host-side TypeScript SDK that talks to a CONDUYT firmware running on the device). Target device firmware runs on this board:
> ```json
> {board_json_minimal}
> ```
> Respond with TypeScript or JavaScript host-side code.

**User message:** a one- to three-sentence natural task description matching the peripheral and task_type. Example phrasings:
- "Read the BME280 over I2C and print temperature every second."
- "Drive a 24-pixel NeoPixel ring with a slow rainbow."
- "Connect to WiFi and POST a JSON payload to a URL once a minute."
- "Subscribe to pin A0 from the host and log readings to console."

The user message should NOT mention the framework explicitly. It should sound like a hardware request, and the framework is inferred from the system message.

**Assistant message:** code response per the voice rules in `synthesis_system.md`. Include all necessary imports/includes. Define pins as named constants when applicable. Use the board's defaults from the capability JSON unless the task forces a different choice (in which case state the choice in one line of explanation above the code).

For framework-specific structure:
- `arduino` -> single `.ino` sketch, full `setup()` + `loop()`.
- `platformio` -> code block 1: `platformio.ini` with `[env:{platformio_env}]`, valid `framework`, `board`, and `lib_deps`. Code block 2: `src/main.cpp` (or .ino) sketch.
- `esp-idf` -> `main/main.c` or `main/<name>.c` with `app_main()`, plus a one-line note about the required component dependencies.
- `conduyt-js` -> a single `.ts` (or `.js`) file using `ConduytDevice.connect(...)` and the appropriate transport + module imports.
- `conduyt-firmware` -> a single `.ino` sketch using `ConduytSerial` / `ConduytMQTT` / etc transports and `device.addModule(...)` / `device.addDatastream(...)` patterns.

Output ONLY the JSON object specified in `synthesis_system.md`.
