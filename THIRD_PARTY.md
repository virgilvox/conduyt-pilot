# Third-party content in the conduyt-pilot training corpus

This file lists upstream sources whose content has been adapted into the
training dataset under `data/seeds/`. Each adaptation preserves the
upstream copyright and license per the source's terms.

## mascarade (electron-rare)

- **Source**: https://github.com/electron-rare/mascarade
- **License**: MIT
- **Files affected**:
  - `data/seeds/v5_mascarade_embedded.jsonl`
  - `data/seeds/v5_mascarade_iot.jsonl`
  - `data/seeds/v5_mascarade_platformio.jsonl`
  - `data/seeds/v5_mascarade_power.jsonl`

23 hand-curated training examples were extracted from the seed-only mode
of the upstream `finetune/datasets/build_*.py` builder scripts. The
extracted content was format-converted from ShareGPT to OpenAI
chat-message schema and the prose was sanitized to ASCII (em-dashes,
en-dashes, micro signs, multiplication signs, arrows, etc. mapped to
ASCII equivalents) for stylistic consistency with the rest of the
corpus. Box-drawing characters and Greek/math symbols inside code
comments were preserved.

The HuggingFace augmentation path (`--with-hf` flag in the upstream
builders) was deliberately NOT enabled.

Each imported example carries a `source` and `license` field in its
JSONL record for traceability:

```json
{
  "messages": [...],
  "kind": "mascarade-<bucket>",
  "source": "https://github.com/electron-rare/mascarade",
  "license": "MIT",
  "license_holder": "L'Electron Rare, 2026"
}
```

### Upstream MIT license

The MIT License text from the mascarade repository:

```
MIT License

Copyright (c) 2026 electron-rare contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
