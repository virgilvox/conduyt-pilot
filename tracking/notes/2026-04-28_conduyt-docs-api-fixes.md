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

## Files modified (9)

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
