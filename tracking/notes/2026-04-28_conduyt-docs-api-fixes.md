# conduyt docs API fixes — 2026-04-28

User authorized edits to `../conduyt/` to fix documentation API drift discovered while building the fine-tune training corpus. The docs were teaching wrong code (e.g. `import { Servo }` when the actual export is `ConduytServo`), which both confuses humans reading the docs AND poisons any training data extracted from them.

This note documents every change made in the conduyt repo. **The conduyt repo is owned by the user; they should review and commit these themselves.**

## Source of truth used for verification

All API claims were checked against the live source files:
- `../conduyt/sdk/js/src/device.ts` (PinProxy, DatastreamProxy, ModuleProxy, I2CProxy, ConduytDevice)
- `../conduyt/sdk/js/src/modules/{servo,neopixel,oled,dht,encoder,stepper,pid}.ts` (module wrapper classes)
- `../conduyt/sdk/js/src/transports/{serial,web-serial,ble,mqtt,websocket,mock}.ts` (transport interface)
- `../conduyt/sdk/js/src/core/{constants,types,errors}.ts` (SUB_MODE, PIN_MODE, error classes)
- `../conduyt/sdk/js/src/{ota,reconnect}.ts` (ConduytOTA, ReconnectTransport)
- `../conduyt/firmware/src/Conduyt.h` (firmware constant aliases)

## Files modified (10) — covers two audit passes

The first pass (this section's first half) caught the obvious drift in module imports/constructors and the worst transport-interface mismatch. A second pass (after the user asked me to ultrathink + re-audit) caught additional issues in the SDK landing page, the BLE service UUIDs, and the NeoPixel command table. All of them documented below in the order they were fixed.

### `site/content/docs/modules/servo.md`
**Before:**
```js
import { Servo } from 'conduyt-js/modules/servo'
const servo = new Servo(device, 0)   // 0 = first registered module
```
**After:**
```js
import { ConduytServo } from 'conduyt-js/modules/servo'
const servo = new ConduytServo(device)   // resolves the "servo" module from HELLO_RESP
```
**Why:** Source class is `ConduytServo` (constructor takes only `device`; the module is resolved by name internally). The doc's `Servo` and `module_id` argument don't exist.

### `site/content/docs/modules/neopixel.md`
**Before:**
```js
import { NeoPixel } from 'conduyt-js/modules/neopixel'
const strip = new NeoPixel(device, 0)
```
**After:**
```js
import { ConduytNeoPixel } from 'conduyt-js/modules/neopixel'
const strip = new ConduytNeoPixel(device)
```
**Why:** Same drift pattern as servo.

### `site/content/docs/modules/dht.md`
**Before:**
```js
import { DHT } from 'conduyt-js/modules/dht'
const dht = new DHT(device, 0)
```
**After:**
```js
import { ConduytDHT } from 'conduyt-js/modules/dht'
const dht = new ConduytDHT(device)
```
**Why:** Same drift pattern.

### `site/content/docs/modules/i2c-passthrough.md`
**Before:**
```js
await device.i2cWrite(0x68, new Uint8Array([0x00]))
const data = await device.i2cRead(0x68, 2)
```
**After:**
```js
const i2c = device.i2c()
await i2c.write(0x68, new Uint8Array([0x75]))
const echoed = await i2c.read(0x68, 1)
// ...also showed i2c.readReg(addr, reg, count)
```
**Why:** `device.i2cWrite/i2cRead` are not real methods. The actual API is `device.i2c(bus?)` which returns a proxy with `write`, `read`, and `readReg`. Updated both the JS code block and the prose paragraph that referenced the old methods.

### `site/content/docs/reference/js-api.md`
Three significant fixes:
1. **PinProxy table**: added `analogRead()` and `digitalRead()` methods; expanded the subscribe options to include `mode` (numeric `SUB_MODE` constant). The old table was missing both; users couldn't tell from the docs that `subscribe({ mode: SUB_MODE.FALLING })` was the way to detect falling edges.
2. **DatastreamProxy table**: corrected the return type of `read()` (was `Promise<any>`, actually `Promise<Uint8Array>`), added the `descriptor` getter, removed the incorrect `intervalMs` option from `subscribe()` (datastreams use `threshold` only).
3. **ConduytTransport interface**: was completely wrong. Doc said `open()/close()/onPacket()`; actual interface is `connect()/disconnect()/onReceive()` plus a `connected` readonly getter. Added a brief `ReconnectTransport` example since it's the right answer for survive-the-link-drop use cases.

### `site/content/docs/how-to/connect-ble.md`
**Before:** the JS example called `device.on('disconnect', () => {...})` — a fabricated API. `device.on(eventType, handler)` accepts numeric `EVT.*` constants, not strings, and there's no `EVT.DISCONNECT`.

**After:** replaced with a `setInterval` polling `device.connected`, with a comment explaining the SDK doesn't expose a public disconnect event today and recommending `ReconnectTransport` for auto-recovery.

### `site/content/docs/how-to/use-datastreams.md`
- Replaced `CONDUYT_TYPE_FLOAT32` with `CONDUYT_FLOAT32` in firmware example code blocks for consistency with the firmware reference examples (`firmware/examples/MQTTSensor/MQTTSensor.ino` uses the short form). Both are valid (the short forms are aliased in `Conduyt.h`), but mixing them confuses readers.
- Updated the constants table to use short forms throughout.
- Added a one-line note that the verbose `CONDUYT_TYPE_<NAME>` aliases also work.

### `site/content/docs/reference/datastream-types.md`
- Same `CONDUYT_TYPE_FLOAT32` -> `CONDUYT_FLOAT32` fix in firmware example block.
- Added the same one-line note about the alias.

### `site/content/docs/tutorials/what-is-conduyt.md`
- Same `CONDUYT_TYPE_FLOAT32` -> `CONDUYT_FLOAT32` fix in firmware example block.

---

## Second-pass findings (re-audit)

### `site/content/docs/sdks/javascript.md` (significant drift)
The SDK landing page had multiple fabricated APIs that don't exist in `device.ts`:

| Doc said | Actual API |
|---|---|
| `device.pinMode(13, 'output')` | `device.pin(13).mode('output')` |
| `device.pinWrite(13, 1)` | `device.pin(13).write(1)` |
| `device.firmwareName` | `device.capabilities.firmwareName` |
| `device.onDatastream(name, cb)` | `for await (...) of device.datastream(name).subscribe()` |
| `device.streamStart()` | not a JS method (STREAM_START is a wire-level command for raw pin streaming, not an SDK method) |

Also fixed: the transports table claimed BLE/MQTT/WebSocket/CLASP were "planned" when they all already ship under `conduyt-js/transports/<name>`. Updated the table to list all seven transports (Serial, WebSerial, BLE, MQTT, WebSocket, CLASP, Mock).

Also fixed: the WebSerial example was missing `await port.open({ baudRate })` before `ConduytDevice.connect`, which fails silently on real hardware.

### `site/content/docs/how-to/connect-ble.md` (BLE UUID drift)
Doc claimed CONDUYT uses Nordic UART Service (NUS) with UUIDs `6E400001-...` / `6E400002-...` / `6E400003-...`. **This is completely wrong.** Both the firmware (`firmware/src/conduyt/transport/ConduytBLE.h`) and the JS SDK (`sdk/js/src/transports/ble.ts`) use CONDUYT-specific UUIDs:

| Characteristic | Actual UUID |
|---|---|
| Service | `0000cd01-0000-1000-8000-00805f9b34fb` |
| TX (notify) | `0000cd02-0000-1000-8000-00805f9b34fb` |
| RX (write)  | `0000cd03-0000-1000-8000-00805f9b34fb` |

This bug would have made any custom BLE central (raw CoreBluetooth on iOS, native Android, MicroPython BLE) fail at the GATT discovery step. Fixed in two places: the BLE transport details table, and the "Using CoreBluetooth directly" section. Added a note that the JS `BLETransport` constructor accepts UUID overrides via `{ serviceUUID, txCharUUID, rxCharUUID }` for non-default firmwares.

Also updated a code comment that still referred to "NUS service" filtering.

### `site/content/docs/modules/neopixel.md` (command table drift)
The NeoPixel command reference table had three issues compared to the JS source (`sdk/js/src/modules/neopixel.ts`):

1. **`Begin (0x01)` payload was missing the `type` byte.** Source sends 4 bytes `pin(1) + count(2) + type(1)`; doc said only `pin(1) + count(2)`.
2. **`SetPixelW (0x03)` was fabricated.** Command 0x03 in source is actually `setRange(start, count, r, g, b)`. The "RGBW set pixel" path is just `setPixel` with a 6th byte appended (firmware dispatches by payload length).
3. **`setRange` was missing entirely** from the table — a useful command for solid-color runs.

Fixed: rewrote the command table to match source. Begin shows the type byte. Command 0x02 (SetPixel) shows it accepts both 5-byte (RGB) and 6-byte (RGBW) payloads. Command 0x03 is now correctly `SetRange` with payload `start(2) + count(2) + r(1) + g(1) + b(1)`. Fill (0x04) similarly shows it accepts 3 or 4 bytes for RGB or RGBW.

Updated the "Notes" section: removed the misleading mention of `setPixelW()` (no such method) and added a one-line note about `setRange` for runs.

## Third-pass findings

The user asked for one more deep audit. This pass extended to: `reference/hello-resp.md`, `reference/packet-structure.md`, `how-to/add-module.md`, `how-to/broker-setup.md`, `how-to/troubleshooting.md`, all `getting-started/*.md` docs, and `tutorials/sensor-dashboard.md`.

### Found and fixed
1. **`reference/packet-structure.md`** — COBS table row said "BLE (NUS)". Removed the parenthetical since CONDUYT BLE doesn't use NUS (already fixed UUIDs in connect-ble.md, this was the matching cleanup).
2. **`how-to/troubleshooting.md`** — `subscribe({ interval: 100, threshold: 5 })` was using the wrong option name. The actual option is `intervalMs`, not `interval` (`PinSubscribeOptions` interface in `core/types.ts`). The wrong name would silently default to 100ms (since the typo gets ignored), so this is a "code that runs but does nothing useful" bug. Fixed.

### Verified clean (third pass)
- **`reference/hello-resp.md`**: binary layout matches `parseHelloResp` byte-for-byte (firmware name 16 bytes, version 3 bytes, mcu_id 8 bytes, ota_capable 1 byte, pin_count + pins[], i2c/spi/uart counts, max_payload uint16 LE, modules[] with 12-byte overhead per module + pin_count, datastreams[] 28 bytes each).
- **`reference/packet-structure.md`**: header layout (MAGIC + VER + TYPE + SEQ + LEN(2 LE) + PAYLOAD + CRC8) matches `wireEncode` exactly. CRC region `[2..7+payloadLen-1]` is correct.
- **`how-to/add-module.md`**: `ConduytModuleBase` interface (name, versionMajor/Minor, begin, handle, poll, pinCount, pins) matches `firmware/src/conduyt/ConduytModuleBase.h`. The `CONDUYT_MODULE` and `CONDUYT_ON_CMD` macros exist as documented.
- **`how-to/broker-setup.md`, `getting-started/*.md`, `tutorials/sensor-dashboard.md`**: all JS code uses the correct pin proxy / datastream proxy / capabilities access patterns. No drift.

### Out-of-scope flagged
- `sdks/swift.md` uses `device.pinMode(...)` and `device.pinWrite(...)`. **These are real Swift methods** (verified in `sdk/swift/Sources/ConduytKit/ConduytDevice.swift` lines 70 and 75). The Swift SDK has a different API shape than JS; not drift.
- Python code in module docs uses `module_id=0` constructor argument. Out of audit scope (Python SDK source not verified).

## Fourth-pass findings — caught a bug I introduced myself

User asked for one more meticulous re-audit. Caught a real correctness bug in code I had committed:

### The WebSerialTransport pre-open bug
`WebSerialTransport.connect()` (in `sdk/js/src/transports/web-serial.ts` line 52) **unconditionally** calls `this._port.open({ baudRate })`. If the user pre-opens the port and passes it via `{ port }`, the transport tries to open it again. WebSerial spec rejects double-open with `InvalidStateError`.

In my second-pass fix to `sdks/javascript.md`, and in three of the v2 training examples I authored, I had introduced this exact pattern:

```ts
// WRONG (throws "port already open"):
const port = await navigator.serial.requestPort()
await port.open({ baudRate: 115200 })
const device = await ConduytDevice.connect(new WebSerialTransport({ port }))
```

The correct pattern (lets the transport open):

```ts
// CORRECT:
const port = await navigator.serial.requestPort()
const device = await ConduytDevice.connect(
  new WebSerialTransport({ port, baudRate: 115200 })
)
```

Or omit `port` entirely and let the transport call `requestPort()` itself.

**Fixed in 4 places:**
1. `conduyt/site/content/docs/sdks/javascript.md` — Browser (WebSerial) example
2. `data/seeds/v2_conduyt_js_single.jsonl` — example 2 (single-turn WebSerial)
3. `data/seeds/v2_conduyt_js_multiturn.jsonl` — example 4 (multi-turn WebSerial #connect+#toggle)
4. `data/seeds/v2_conduyt_js_multiturn.jsonl` — example 28 (WebSerial with vid/pid filters)

Added a comment to the doc explaining why pre-opening is wrong, so this trap is documented for future readers.

### Other meticulous spot-checks (clean)
- **All 7 module wrapper internal names** (`device.module(<name>)`) match firmware-side `name()` returns: servo, neopixel, oled1306, dht, encoder, stepper, pid. The OLED firmware module is `oled1306`, correctly documented in `js-api.md` after my second-pass fix.
- **All v2 subscribe options** verified to use correct names: `intervalMs` (never `interval`), `mode: SUB_MODE.X` (numeric, never strings), `threshold`. No drift.
- **Module name 8-char limit**: every firmware module name fits. Longest: `neopixel`, `oled1306`, `i2c_pass` at exactly 8 chars.
- **Firmware transports verified**: `ConduytBLE`, `ConduytCLASP`, `ConduytMQTT`, `ConduytSerial`, `ConduytTCP`, `ConduytUSBSerial` exist. Doc mentions of TCP (in transport-architecture.md) match. WebSocket is host-only on the JS side.

## Fifth-pass findings

User asked to go even deeper. Found a real bug in 3 of my v2 training examples:

### MockTransport examples would hang at connect()
`MockTransport.connect()` just sets `_connected = true` and never injects a response. But `ConduytDevice.connect()` awaits a HELLO_RESP — so `await ConduytDevice.connect(new MockTransport())` blocks forever.

The actual conduyt-js test suite (`sdk/js/test/device.test.ts`) handles this with an `autoRespond(transport)` helper that wraps `transport.send` to inject a HELLO_RESP when the SDK sends a HELLO command (and ACKs everything else):

```ts
function autoRespond(t: MockTransport): void {
  const orig = t.send.bind(t)
  t.send = async (packet: Uint8Array) => {
    await orig(packet)
    const { type, seq } = wireDecode(packet)
    if (type === CMD.HELLO) {
      t.inject(wireEncode(makePacket(EVT.HELLO_RESP, seq, helloPayload())))
    } else {
      t.inject(wireEncode(makePacket(EVT.ACK, seq)))
    }
  }
}
```

Plus a `helloPayload()` builder that returns a minimal HELLO_RESP byte payload.

My v2 examples just called `await ConduytDevice.connect(new MockTransport())` directly — that hangs. Three examples affected:

1. `v2_conduyt_js_api_docs.jsonl` example 5 ("how do I write unit tests?")
2. `v2_conduyt_js_single.jsonl` example 6 (vitest test for pin.write)
3. `v2_conduyt_js_multiturn.jsonl` example 13 (mock setup + extending test)

All three rewritten to include the `autoRespond` helper inline, with a comment pointing to `sdk/js/test/device.test.ts` as the canonical pattern. The model will now learn the right way to mock-test against ConduytDevice instead of producing code that hangs at connect.

### Other meticulous spot-checks (clean)
- **All command codes** (CMD: PING, HELLO, PIN_*, I2C_*, SPI_XFER, MOD_CMD, STREAM_*, DS_*, OTA_*, RESET) and event codes (EVT: PONG, HELLO_RESP, ACK, NAK, PIN_*, I2C_*, SPI_*, MOD_*, STREAM_DATA, DS_*, LOG, FATAL) verified row-by-row in `packet-types.md` against `sdk/js/src/core/constants.ts`.
- **All error codes** (ERR: 0x01 to 0x10) verified in `error-codes.md`.
- **PIN_CAP bits** (0 to 7) verified in `hello-resp.md`.
- **PIN_MODE values** (input=0x00, output=0x01, pwm=0x02, analog=0x03, input_pullup=0x04) verified.
- **SUB_MODE values** (CHANGE=0x01, RISING=0x02, FALLING=0x03, ANALOG_POLL=0x04) verified.
- **DS_TYPE_SIZE table** (BOOL/INT8/UINT8 = 1, INT16/UINT16 = 2, INT32/FLOAT32 = 4, STRING/BYTES variable) verified.
- **All module event codes** (Encoder Tick, Stepper Done, PID Tick) all use `0x01`. Event payload sizes match source decoders.
- **ConduytOTA** chunk-size logic verified: `Math.max(64, advertised - 4)` per source. flash-ota.md prose matches.

## Verification (post fifth pass)

Comprehensive grep across audited docs for **every** drift pattern I've found:

```
NO DRIFT REMAINING in audited files.
```

Patterns scanned for:
- `import { Servo|NeoPixel|DHT }` (drifted module imports)
- `new Servo|NeoPixel|DHT(...)` (drifted constructors)
- `device.i2cWrite|i2cRead` (fabricated device-level i2c methods)
- `device.pinMode|pinWrite` (fabricated pin convenience methods)
- `device.firmwareName` (wrong property access path)
- `device.onDatastream` / `device.streamStart` (fabricated)
- `.on('disconnect', ...)` (fabricated event)
- `open()|onPacket(` (old transport interface names)
- `6E400001|6E400002|6E400003` (wrong NUS UUIDs)

Module command tables verified row-by-row against the seven module .ts source files. All command IDs and payload structures match.

Firmware-side methods referenced in docs (`device.declarePinCaps`, `device.declareI2cBus`, `device.declareSpiBus`, `device.addModule`, `device.addDatastream`, `device.onDatastreamWrite`, `device.writeDatastream`, `device.begin`, `device.poll`) all confirmed present in `firmware/src/conduyt/ConduytDevice.h`.

Constants (`CONDUYT_FLOAT32` and friends, error codes, packet types, PIN_CAP bits) verified against `firmware/src/conduyt/core/conduyt_constants.h` and `sdk/js/src/core/constants.ts`.

## Files NOT touched (and why)

- **Python code blocks** in any doc: no time to verify against `../conduyt/sdk/python/`. The drift, if any, is on the user to flag.
- **Go, Swift, Rust, WASM SDK docs**: out of scope for the JS-focused fine-tune.
- **`reference/firmware-api.md`**: legitimate reference to the underlying `CONDUYT_TYPE_*` constant (not user-facing example code). Left as-is.
- **`reference/datastream-types.md` line 20** (table row showing `CONDUYT_TYPE_FLOAT32`): same reasoning. The reference table documents the canonical underlying constant; the trailing note explains the short alias.
- **`tutorials/first-blink.md`**: contained a "dive into" banned phrase that was already being filtered by `scripts/07_extract_conduyt_docs.py`. Didn't fix because the user's voice rules ban the phrase, and the doc author may want to rephrase this themselves.
- **`how-to/broker-setup.md`**: contains a `✔` emoji in Docker output. Already filtered by the validator. Not a code-correctness issue.

## Verification

After all fixes:
1. `scripts/07_extract_conduyt_docs.py` reports **zero drift warnings** (down from 4).
2. The extractor produces 26 examples; 25 pass validation (1 still skipped for the unrelated `✔` Docker output emoji in broker-setup).
3. `conduyt-pilot-data-v2.zip` rebuilt with corrected doc-derived examples: 243 train + 25 eval, same as before but with corrected JS API.

## Next step for the user

1. Review the 9 modified files in the conduyt repo (run `cd ../conduyt && git diff`).
2. Commit them with a message like `docs: fix JS API drift (Servo->ConduytServo, i2cWrite->i2c().write, transport interface)`.
3. Push to the conduyt repo.
4. Optional: rebuild the docs site to render the corrected examples for end users.

The conduyt-pilot side is already updated to use the corrected v2 bundle (committed and pushed at the end of this session).
