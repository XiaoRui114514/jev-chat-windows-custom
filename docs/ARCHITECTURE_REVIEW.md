# v0.1.12 baseline review and implementation plan

Baseline: upstream tag `v0.1.12`, commit `c6d3a10`. The original Git history,
MIT LICENSE and NOTICE are retained. This review preceded source changes.

## Existing call chain

`main.py` owns Qt callbacks and per-chat history. A spawned `app.worker` owns
Windows Graphics Capture (`app.capture.Capture`), chat-area geometry and title
OCR. `app.ocr.Reader` selects RapidOCR for Chinese/English and Windows OCR for
Korean/Japanese profiles, classifies text by pixel background/contrast, merges
nearby OCR lines and deduplicates strings. Worker tuples become history tuples.
`core.engine.analyze` builds state, asks seven Jev decisions, drafts candidates
through `core.draft` / `core.llm`, asks Jev to rank, and returns three candidates.
`app.fill` writes clipboard, focuses the input box and uses Ctrl+V; it never
sends Enter. `app.overlay` is the existing Fluent Qt UI; `app.debugwin` draws
OCR classifications. Text/network work runs outside the Qt thread.

`core.providers.py` contains provider metadata, while `core.jev_client` dispatches
TypeSafe SDK or OpenRouter Decisions HTTP and `core.llm` adapts three SDKs.
`app.settings` rereads config.json and persists two API keys to user environment
variables. There are module-level offline self-tests, but no collected test suite.
`jev.spec` collects OCR models, Qt resources, SDKs and Windows capture binaries;
local `build.bat` and Actions use the same onedir spec. CI uses Python 3.11;
RapidOCR 1.4 requires Python below 3.13.

## Changes in upstream releases

v0.1.10 → v0.1.11: nonblocking environment notifications during key saving,
product naming and attribution/documentation changes. v0.1.11 → v0.1.12:
per-app capture/OCR profiles, Korean Windows OCR, KakaoTalk pinned-notice
filtering, Chinese/Korean UI translations, persistent language selection and
live language switching without discarding state. These features must survive.

## Old custom-jev implementation verified from code

`src/core/jev_client.py` implements custom OpenAI chat/completions requests,
model-list GET, fenced JSON extraction, typed noul/choice/score validation,
partial-answer acceptance and failure when no answer is usable. TypeSafe custom
base uses the official SDK and supports manually typed model IDs when a mirror
does not expose a list. `src/core/providers.py` supplies both custom choices;
`src/app/settings.py` persists jev_base_url; `src/app/overlay.py` adds its inputs;
`src/main.py` and `src/core/engine.py` forward the argument to judging and ranking.
`tools/test_patch.py` exercises a local fake server and SDK boundaries.
`tools/build_patch.py` replaces compiled modules in Python 3.11 PYZ/CArchive;
`patch/apply.ps1` enforces EXE hashes. These patch/build mechanisms will not be
carried into this fork. The local shortcut's EXE hash matches the patched v0.1.11
manifest, so it is a valid old-behavior reference, not the new build input.

## Problems and boundaries

- Reader discards non-flat image text and cannot emit image-only messages.
- Sender names can leak across bubbles when a name is not recognized.
- Exact pixel color counts are brittle on rescaled/compressed images.
- Spatial-only line joining can combine adjacent separate bubbles.
- Similarity-only deduplication swallows repeated identical messages.
- Settings save reconstructs a fixed dict, discarding future/custom fields;
  writes are not atomic. Some errors are silent or expose server body text.
- One image cannot prove video playback, article body or GIF motion. A still
  frame can only describe a visible card/thumbnail; unknown stays unknown.

## Provided screenshot observations (local/private; do not publish originals)

Two video-channel crops have left avatars, a gap, rounded vertical cards,
central circular play overlays and a bottom channel symbol/author row. One
thumbnail includes text at its top. The article crop has a left avatar, a wide
dark-gray card, two title lines, a small right thumbnail and a footer source
row. Avatar is outside the media crop. Card/thumbnail text is not ordinary
bubble conversation. Scale-relative bounds and anchor relationships are needed;
tests must include rescaling and an ambiguous generic video negative case.

## Chosen architecture

Preserve working capture/UI/SDK and Jev stages. Convert provider metadata into
`core/providers/` with a decision-provider registry. Keep `core.jev_client` as a
compatibility facade. Separate typed-answer validation and safe errors.
Add `core/message` (data model, context, dedup), `core/parser` (local geometry,
sender anchors and type), `core/ocr` (conservative cleaning/preprocessing),
`core/media` (gated cropped vision and bounded TTL/LRU cache) and `core/emoji`
(local semantics and a separate optional contextual intent stage).
`app.ocr.Reader` orchestrates offline recognition; worker transports structured
messages and only selected new media crops. Main performs optional network
enrichment outside Qt, then the existing judge → draft → rank pipeline.

All remote media/complex-emoji switches default off. Plain text and standard
emoji require no new API calls. Vision uses independent OpenAI-compatible
settings and VISION_API_KEY; only cropped media leaves memory. Cache is bounded,
no screenshots/history are written automatically, errors redact keys and avoid
echoing request bodies. Debug shows message bounds, confidence, timing, API
counts and the structured context. Use generated nonprivate fixtures in Git;
run provided private crops locally as additional evidence.

Validation: collected offline tests plus local HTTP contract tests, real OCR
on generated text/private crops, Qt interaction tests, clipboard/fill event
regression against a controlled window, source and packaged smoke runs, local
PyInstaller build and Windows Actions. Real recipient sending is never tested.
