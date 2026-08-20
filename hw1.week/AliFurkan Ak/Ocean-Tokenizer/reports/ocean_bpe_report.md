# BPE Tokenizer Report — Ocean

## 1. Dataset Summary

Source: `data/ocean_corpus.txt` (built from the Wikipedia "Ocean" article via the MediaWiki API).

- **Total characters:** 56,389
- **Total words:** 9,149
- **Corpus file:** `C:\Users\90535\source\magibu\Ocean-Tokenizer\data\ocean_corpus.txt`

## 2. Training Parameters

| Parameter | Value |
|---|---|
| Algorithm | Byte-level BPE (`tokenizers`) |
| vocab_size (target) | 1024 |
| actual vocab size | 1024 |
| min_frequency | 2 |
| special tokens | <pad>, <unk>, <bos>, <eos> |
| pre-tokenizer | ByteLevel (256-byte base alphabet) |
| post-processor | `<bos> ... <eos>` framing |

## 3. Learned Example Tokens

Tokens produced by merges that map to more than one character (`␣` = leading word-boundary space):

| ID | Token |
|---|---|
| 261 | `he` |
| 264 | `in` |
| 265 | `␣the` |
| 266 | `re` |
| 267 | `an` |
| 268 | `at` |
| 269 | `er` |
| 270 | `on` |
| 271 | `ce` |
| 275 | `al` |
| 276 | `nd` |
| 277 | `en` |
| 278 | `es` |
| 279 | `␣of` |
| 280 | `is` |
| 281 | `ar` |
| 283 | `␣and` |
| 286 | `␣in` |
| 287 | `ic` |
| 288 | `cean` |
| 289 | `it` |
| 292 | `ion` |
| 293 | `or` |
| 294 | `␣ocean` |
| 295 | `ro` |
| 296 | `ed` |
| 297 | `ing` |
| 298 | `as` |
| 299 | `ur` |
| 301 | `ater` |
| 303 | `␣to` |
| 304 | `␣is` |
| 305 | `ct` |
| 307 | `ly` |
| 308 | `id` |
| 309 | `␣water` |
| 311 | `ent` |
| 312 | `␣re` |
| 313 | `nt` |
| 314 | `␣The` |

## 4. Encode / Decode Examples

**Sentence:** The Pacific is the largest and deepest of the world's oceans.

- Token count: **18**
- Tokens: `<bos> | T | he | ␣Pacific | ␣is | ␣the | ␣lar | gest | ␣and | ␣deep | est | ␣of | ␣the | ␣world | 's | ␣oceans | . | <eos>`
- Round-trip decode: ✅ exact match

**Sentence:** Ocean currents distribute heat around the globe.

- Token count: **16**
- Tokens: `<bos> | O | cean | ␣currents | ␣dist | ri | b | ut | e | ␣heat | ␣around | ␣the | ␣glob | e | . | <eos>`
- Round-trip decode: ✅ exact match

**Sentence:** Marine ecosystems depend on phytoplankton for oxygen production.

- Token count: **25**
- Tokens: `<bos> | M | ar | ine | ␣ec | osy | stem | s | ␣depend | ␣on | ␣ph | y | t | op | l | an | k | t | on | ␣for | ␣oxygen | ␣produ | ction | . | <eos>`
- Round-trip decode: ✅ exact match

**Sentence:** Tides are caused by the gravitational pull of the Moon and Sun.

- Token count: **23**
- Tokens: `<bos> | T | ides | ␣are | ␣caus | ed | ␣by | ␣the | ␣gra | v | it | ational | ␣p | ul | l | ␣of | ␣the | ␣Moon | ␣and | ␣S | un | . | <eos>`
- Round-trip decode: ✅ exact match

## 5. Compression / Observations

- Total words: **9,149**
- Total tokens: **18,073**
- **Average tokens / word: 1.975**
- Per-line average ratio: 1.975
