# Pipeline API Contract

**Status:** Production Specification — v1.0
**Document owner:** Frontend / Pipeline Engineer
**Last updated:** 2026-08-03
**Applies to:** `frontend/pipelines/archmind_pipeline.py`
**Prerequisite for:** F2 implementation

Items marked **⚠ VERIFY AT F1** are behavioral characteristics that depend on the locked OpenWebUI version and must be confirmed against the running deployment before F2 code is written. These items are also tracked in the Implementation Readiness Checklist (Section C).

---

## 1. Pipeline Class Contract

### Purpose

Defines the exact Python class structure that the OpenWebUI Pipelines server expects to find in any file it loads from the pipelines mount directory. Any deviation from this structure causes the Pipelines server to reject the file silently or raise a load error.

### Requirements

| Requirement | Specification |
|---|---|
| Module-level class | `class Pipeline:` must be defined at the top level of the module — not nested, not inside a function |
| `name` attribute | String class attribute. Displayed in OpenWebUI's model selector dropdown. Must be `"ArchMind AI"` |
| `version` attribute | String class attribute in `MAJOR.MINOR.PATCH` format. Displayed in admin panel Pipelines page |
| `Valves` nested class | `class Valves(BaseModel):` defined as a nested class inside `Pipeline`. Must inherit from `pydantic.BaseModel`. Defines all admin-configurable runtime fields |
| `valves` instance attribute | `self.valves = self.Valves()` initialized in `__init__`. Holds the live Valves values used at runtime |
| `pipe()` method | Required. The entry point OpenWebUI calls for every user message. Must be defined — the Pipelines server will fail to register the pipeline without it |
| `__init__()` method | Required. Must initialize `self.valves`. Any other startup logic that should not repeat on every `pipe()` call belongs here |

### Constraints

- The class must be named exactly `Pipeline` — case-sensitive. OpenWebUI scans for this name.
- No other class in the same file may be named `Pipeline`.
- Class-level string attributes (`name`, `version`) must be defined at class scope, not inside `__init__`. OpenWebUI reads them before instantiation.
- **⚠ VERIFY AT F1:** Whether a `type` class attribute is required by the locked version (some versions require `type = "pipe"` or `type = "manifold"`).

### Example (structural contract — not implementation)

```
Class: Pipeline
  Class attributes:
    name: str = "ArchMind AI"
    version: str = "1.0.0"
    type: str  ← VERIFY AT F1: required? value?

  Nested class:
    Valves(BaseModel)
      [see Section 3]

  Instance attributes (set in __init__):
    self.valves: Valves

  Methods:
    __init__(self) → None
    pipe(self, ...) → AsyncGenerator[str, None]
    on_startup(self) → Awaitable[None]         [optional but recommended]
    on_shutdown(self) → Awaitable[None]        [optional]
    on_valves_updated(self) → Awaitable[None]  [optional]
```

### Acceptance Criteria

- Pipelines server starts without errors when `archmind_pipeline.py` is present in the mount directory
- Pipeline appears in the OpenWebUI model selector under the name `"ArchMind AI"`
- Version string `"1.0.0"` is visible in the admin panel Pipelines page
- ValvesForm is rendered in the admin panel for this pipeline (confirms `Valves` class was found)

---

## 2. Required Methods

### Purpose

Specifies the exact method signatures that OpenWebUI invokes, the parameters it passes, the return types it accepts, and the optional lifecycle hooks the pipeline may implement.

### Requirements

#### 2.1 `pipe()` — Required

The primary method. Called on every user message sent to the pipeline model.

| Attribute | Specification |
|---|---|
| Name | `pipe` |
| Signature | `pipe(self, user_message: str, model_id: str, messages: list[dict], body: dict)` |
| Return type | `AsyncGenerator[str, None]` — async generator yielding string chunks |
| Async | Yes — must be defined with `async def` |
| Called by | OpenWebUI on every user message to the pipeline model |
| Called how often | Once per user message. Multiple messages in a conversation = multiple `pipe()` calls |

**Parameters:**

| Parameter | Type | Contents |
|---|---|---|
| `user_message` | `str` | The text of the user's most recent message only. Used as the primary input for URL extraction. |
| `model_id` | `str` | The pipeline model ID as registered in OpenWebUI. Not used by ArchMind pipeline logic. |
| `messages` | `list[dict]` | Full conversation history in OpenAI chat format: `[{"role": "user"/"assistant", "content": "..."}]`. Ordered oldest-first. Last entry is the current user message. |
| `body` | `dict` | Full request body from OpenWebUI. Contains model, messages, stream flag, and any extra metadata. May contain `conversation_id` — **⚠ VERIFY AT F1** (key name and presence). |

#### 2.2 `on_startup()` — Recommended

Called once when the Pipelines server loads the pipeline file (at server startup or when the file is hot-reloaded). Use for one-time initialization: pre-warming HTTP connections, validating Valve configuration, logging startup state.

| Attribute | Specification |
|---|---|
| Signature | `on_startup(self)` |
| Return type | `None` (or `Awaitable[None]` if async) |
| Called by | Pipelines server on file load |
| Called how often | Once per server startup or hot-reload event |

#### 2.3 `on_shutdown()` — Optional

Called when the Pipelines server is shutting down. Use for cleanup: closing HTTP client sessions.

| Attribute | Specification |
|---|---|
| Signature | `on_shutdown(self)` |
| Return type | `None` (or `Awaitable[None]` if async) |

#### 2.4 `on_valves_updated()` — Optional but recommended

Called when an admin saves updated Valve values in the admin panel. The new values are already applied to `self.valves` before this method is called. Use to re-validate configuration (e.g., test the new `ARCHMIND_API_URL` is reachable).

| Attribute | Specification |
|---|---|
| Signature | `on_valves_updated(self)` |
| Return type | `None` (or `Awaitable[None]` if async) |

### Constraints

- `pipe()` must yield at least one string before any blocking I/O (the AnalysisHeader Phase 1 yield must precede the `POST /jobs` call — see Section 7).
- `pipe()` must handle all expected error conditions by yielding an ErrorCard (see Section 8), not by raising exceptions.
- Unhandled exceptions raised from `pipe()` surface to the user as raw error text — this is an unacceptable user experience. All code paths must be wrapped.
- **⚠ VERIFY AT F1:** Whether `on_startup()` must be `async def` or plain `def` in the locked version.

### Acceptance Criteria

- Submitting a message to the pipeline model in OpenWebUI triggers exactly one `pipe()` call
- `on_startup()` is called once at pipeline load, not once per user message
- `on_valves_updated()` is called when Valves are saved in the admin panel, confirmed by a log entry
- No unhandled exceptions escape `pipe()` under any tested input condition

---

## 3. Valves Schema

### Purpose

Defines the runtime configuration fields that the ArchMind pipeline exposes to OpenWebUI's admin panel. Valves are the only mechanism for configuring the pipeline at runtime without redeploying. The `ARCHMIND_API_KEY` stored in Valves is the sole authentication secret — it must never appear in browser-side code, URL parameters, or logs.

### Requirements

| Field | Type | Default | Description |
|---|---|---|---|
| `ARCHMIND_API_URL` | `str` | `"http://backend:8000"` | Base URL of the ArchMind backend. On the same Docker network, `backend` resolves to the backend container. Change to the production URL at F5. |
| `ARCHMIND_API_KEY` | `str` | `""` | The `X-API-Key` value for all protected backend endpoints. Must be ≥ 32 characters (matches `backend/config/settings.py` `validate_api_key`). Must never be logged. |
| `POLL_INTERVAL_SECONDS` | `int` | `5` | Seconds between `GET /api/v1/jobs/{job_id}` poll requests. Minimum 1. Recommended range: 3–15. |
| `MAX_POLL_DURATION_SECONDS` | `int` | `1800` | Hard timeout for the poll loop in seconds (30 minutes). When exceeded, the pipeline yields a `timeout` ErrorCard and stops polling. |

### Constraints

- All Valves fields must have default values. A Valve field without a default causes the Pipelines server to fail to instantiate the class.
- `ARCHMIND_API_KEY` default is an empty string `""`. The pipeline must detect this condition in `pipe()` and yield a configuration error before attempting any HTTP call.
- **⚠ VERIFY AT F1:** Whether `ARCHMIND_API_KEY` (a `str` field) is rendered as a password input (masked) in the admin panel, or as plain text. If plain text, access to the admin panel's Pipelines page must be restricted to trusted operators only. This is a security requirement.
- **⚠ VERIFY AT F1:** Whether Pydantic field validators (e.g., `ge=1` for `POLL_INTERVAL_SECONDS`) are enforced at admin save time, or only at class instantiation.
- Valve field names are conventionally ALL_CAPS in OpenWebUI Pipelines. Follow this convention for consistency.

### Example (Valves schema specification)

```
Valves(BaseModel):
  ARCHMIND_API_URL:
    type:        str
    default:     "http://backend:8000"
    validation:  must start with "http://" or "https://"
    admin form:  text input
    label:       "ArchMind API URL"

  ARCHMIND_API_KEY:
    type:        str
    default:     ""
    validation:  length >= 32 when non-empty
    admin form:  password input [VERIFY AT F1]
    label:       "ArchMind API Key"
    security:    NEVER log this value

  POLL_INTERVAL_SECONDS:
    type:        int
    default:     5
    validation:  >= 1
    admin form:  number input
    label:       "Poll Interval (seconds)"

  MAX_POLL_DURATION_SECONDS:
    type:        int
    default:     1800
    validation:  >= 60
    admin form:  number input
    label:       "Max Poll Duration (seconds)"
```

### Acceptance Criteria

- ValvesForm in admin panel shows all 4 fields with their default values
- Saving updated Valve values takes effect on the next `pipe()` call without pipeline restart
- `ARCHMIND_API_KEY` is confirmed not to appear in Pipelines server logs at any log level
- Empty `ARCHMIND_API_KEY` causes a configuration error message in the pipeline response, not a raw HTTP 401 error
- **⚠ VERIFY AT F1:** `ARCHMIND_API_KEY` renders as masked input or documented restriction is applied

---

## 4. OpenWebUI Lifecycle

### Purpose

Describes when and how OpenWebUI and the Pipelines server create, invoke, and destroy the `Pipeline` object. This lifecycle has direct implications for state management — specifically, whether instance variables (used for the per-conversation job guard) persist across `pipe()` calls.

### Requirements

#### 4.1 Instantiation model

**⚠ VERIFY AT F1 — critical for job guard design.**

Two possible models exist:

| Model | Description | Implication for job guard |
|---|---|---|
| **Singleton** | One `Pipeline` instance is created when the file is loaded. All `pipe()` calls across all conversations share the same instance. | Instance variables persist across calls. A `dict` keyed by `conversation_id` can track active jobs per conversation. |
| **Per-request** | A new `Pipeline` instance is created for each `pipe()` call. Instance variables are reset on every call. | Instance variables cannot persist state. An external store (file, shared dict, database) is required for the job guard. |

The F2 engineering investigation (per Part 9) must determine which model applies and document the result in this section before F4 implements the production job guard.

**Placeholder — fill at F2:**
```
Instantiation model: [SINGLETON / PER-REQUEST]
Verified on OpenWebUI version: [version]
Evidence: [log output or source reference]
```

#### 4.2 Load sequence

```
Pipelines server starts
  → Scans mount directory for .py files
  → For each file: imports module, locates class Pipeline
  → Calls Pipeline.__init__()        ← once
  → Calls Pipeline.on_startup()      ← once [VERIFY: sync vs async]
  → Registers pipeline in model list

Admin updates Valves:
  → Applies new values to self.valves
  → Calls Pipeline.on_valves_updated()

User sends message in OpenWebUI:
  → OpenWebUI routes to Pipelines server
  → Pipelines server calls Pipeline.pipe(user_message, model_id, messages, body)
  → Pipeline yields string chunks back to OpenWebUI
  → OpenWebUI streams chunks to the user's browser

Pipelines server shuts down:
  → Calls Pipeline.on_shutdown()     ← once [VERIFY: sync vs async]
```

#### 4.3 Hot-reload behavior

When `archmind_pipeline.py` is saved during development, the Pipelines server detects the file change and reloads the module. Hot-reload triggers: module re-import → new `Pipeline` instantiation → `on_startup()` call. Any in-progress `pipe()` calls at the moment of reload may be interrupted.

### Constraints

- State that must persist between conversations (e.g., active job tracking for the job guard) must not rely on instance variables if the per-request model is confirmed at F1.
- `__init__()` must complete quickly — it runs before the Pipelines server marks the pipeline as ready. Heavy initialization (HTTP calls, file reads) belongs in `on_startup()`.
- **⚠ VERIFY AT F1:** Whether hot-reload interrupts in-flight `pipe()` generators or waits for them to complete.

### Acceptance Criteria

- Instantiation model (singleton vs per-request) is confirmed and documented in this section at F2
- `__init__()` completes in under 100ms
- `on_startup()` is called exactly once per server start or hot-reload
- Hot-reload behavior (interrupt vs drain) is confirmed and documented

---

## 5. Input Contract

### Purpose

Defines the exact shape, encoding, and constraints of the inputs the `pipe()` method receives from OpenWebUI. The pipeline must validate these inputs before any downstream processing.

### Requirements

#### 5.1 `user_message: str`

The text of the user's most recent message. This is the primary input to the URL extraction step.

| Attribute | Specification |
|---|---|
| Type | `str` |
| Encoding | UTF-8 |
| Contents | The user's raw message text, as typed. May include leading/trailing whitespace. |
| Empty string | Possible. Pipeline must handle gracefully — yield a usage hint, do not attempt URL extraction. |
| Whitespace-only | Possible. Treat as empty — same handling as empty string. |
| Multi-line | Possible. URL may appear anywhere in the text. The URL extractor must scan the full string. |
| Maximum length | Not bounded by the pipeline — OpenWebUI may pass very long messages. The URL extractor should find the first valid GitHub URL and stop. |

#### 5.2 `messages: list[dict]`

Full conversation history in OpenAI chat format.

| Attribute | Specification |
|---|---|
| Type | `list[dict]` |
| Format | Each entry: `{"role": "user" or "assistant", "content": "..."}` |
| Order | Oldest-first. Last entry is the current user message. |
| Usage | Not used by ArchMind pipeline at v1.0. Reserved for future context-aware features. |
| Empty | Possible on first message. Pipeline must not assume non-empty. |

#### 5.3 `model_id: str`

The pipeline model identifier as registered in OpenWebUI. Not used by the ArchMind pipeline — the target ArchMind backend URL and key come from Valves, not from the model ID.

#### 5.4 `body: dict`

The full OpenWebUI request body. May contain additional metadata.

| Key | Type | Usage |
|---|---|---|
| `model` | `str` | Model identifier — same as `model_id` parameter |
| `messages` | `list[dict]` | Same as `messages` parameter |
| `stream` | `bool` | Whether the client expects streaming. Should always be `True` for ArchMind — **⚠ VERIFY AT F1** if OpenWebUI always sets this to `True` for pipeline models |
| `conversation_id` | `str` (UUID) | **⚠ VERIFY AT F1:** Key name, presence, and format. Required for per-conversation job guard. |

### Constraints

- The pipeline must not trust `user_message` as a valid GitHub URL without running it through the URL extractor.
- The pipeline must handle `messages` being an empty list (first message in a conversation).
- The pipeline must handle `body` containing unexpected keys without raising a `KeyError` — use `.get()` with defaults for all `body` access.
- `ARCHMIND_API_KEY` must never be written into any log alongside the request inputs.

### Example (input payload shape)

```
user_message: "https://github.com/pallets/flask"

messages: [
  {"role": "user", "content": "https://github.com/pallets/flask"}
]

model_id: "archmind_pipeline"

body: {
  "model": "archmind_pipeline",
  "messages": [...],
  "stream": true,
  "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"  ← VERIFY KEY NAME
}
```

### Acceptance Criteria

- Empty `user_message` yields a usage hint message, not an error traceback
- Whitespace-only `user_message` is treated identically to empty
- A URL embedded in a longer message (e.g., `"Please analyse https://github.com/pallets/flask for me"`) is correctly extracted
- Unexpected keys in `body` do not raise `KeyError`
- `conversation_id` (or equivalent) key name is confirmed at F1 and documented here

---

## 6. Output Contract

### Purpose

Defines the return type, yield format, and completion semantics of the `pipe()` method. OpenWebUI must be able to consume the pipeline's output without error.

### Requirements

#### 6.1 Return type selection

ArchMind uses an **async generator** as the return type. This is the only type that supports progressive streaming of long-running analysis results.

| Return type | Description | Used by ArchMind? |
|---|---|---|
| `str` | Single complete string. OpenWebUI renders as one block. | No — no streaming, blocks until analysis complete |
| `list[str]` | List of strings, rendered as one block. | No — no streaming |
| `Iterator[str]` | Sync generator. Streams chunks. | No — prefer async |
| `AsyncGenerator[str, None]` | Async generator. Streams chunks. | **Yes** |

**⚠ VERIFY AT F1:** Confirm `AsyncGenerator` return type is supported in the locked Pipelines version. Confirm `async def pipe()` with `yield` is the correct declaration form.

#### 6.2 Yield value contract

Every value yielded from `pipe()` must be a `str`. Non-string yields (e.g., `bytes`, `dict`, `None`) cause OpenWebUI to raise a serialization error or display garbled output.

| Attribute | Specification |
|---|---|
| Type | `str` only |
| Encoding | UTF-8 |
| Minimum length | No minimum — single-character yields are valid |
| Maximum length | No hard limit — but 512 chars is the ArchMind standard chunk size for report body (Section D5) |
| Content | Valid UTF-8 Markdown text. No raw HTML. No `<style>` blocks. No `<script>` tags. |
| Empty string `""` | **Do not yield empty strings.** Some OpenWebUI versions render an empty string as a visible gap or cause buffering issues. Yield at minimum `"\n"` as a keepalive if a non-content yield is required. |

#### 6.3 Generator completion

The async generator completes when `pipe()` returns (falls off the end of the function or reaches a `return` statement inside an `async def`). OpenWebUI closes the stream on the client side. The user sees the full response.

#### 6.4 Yield ordering requirement

The order in which `pipe()` yields strings is the exact order in which they appear in the OpenWebUI response. There is no buffering or reordering. The first yield is the first content the user sees.

**Critical ordering constraint:** The AnalysisHeader Phase 1 yield (`## ArchMind AI — Submitting...\n`) must be the **first yield** from `pipe()`. It must be yielded before any I/O (including the `POST /jobs` call). This ensures the user sees immediate feedback even if the backend is slow to respond.

### Constraints

- Never yield `None`.
- Never yield a `bytes` object.
- Never yield a `dict` or any non-`str` type.
- The generator must eventually complete — an infinite loop without a termination condition will hold the connection open indefinitely.
- If an unrecoverable error occurs, yield an ErrorCard (see Section 8) and return. Do not raise an exception from within the generator.

### Example (yield sequence overview)

```
pipe() yield sequence for a successful analysis:

  Yield 1: AnalysisHeader Phase 1 ("## ArchMind AI — Submitting...\n\n**Repository:** repo-name\n")
  [POST /jobs called here — blocks until 202 or error]
  Yield 2: AnalysisHeader Phase 2 ("**Job ID:** `{id}`\n**Submitted:** {ts}\n\n---\n")
  [Poll loop begins]
  Yield 3..N: ProgressChecklist + keepalive lines (one per poll cycle)
  [COMPLETE received]
  [GET /reports/{id} called — blocks until response]
  Yield N+1: MetadataCard Markdown
  Yield N+2: TableOfContents Markdown
  Yield N+3..M: Report body in 512-char chunks
  [generator returns — stream closes]
```

### Acceptance Criteria

- All yields from `pipe()` are `str` type — confirmed by unit tests
- First yield occurs before any HTTP call to the backend — confirmed by test timing
- Generator completes (does not hang) on COMPLETE, FAILED, and timeout paths
- OpenWebUI renders the streamed output without visible errors or broken formatting

---

## 7. Markdown Streaming Contract

### Purpose

Defines the content rules for all Markdown yielded by the pipeline. OpenWebUI renders pipeline output as Markdown in the chat interface. This contract ensures output is consistent, accessible, and within the rendering capabilities of plain Markdown.

### Requirements

#### 7.1 Allowed Markdown constructs

| Construct | Allowed | Example |
|---|---|---|
| ATX headings (`##`, `###`) | Yes | `## ArchMind AI — Analysis Complete` |
| Bold (`**text**`) | Yes | `**Repository:**` |
| Italic (`*text*`) | Yes | `*Connecting to backend...*` |
| Inline code (`` `text` ``) | Yes | `` **Job ID:** `3fa85f64...` `` |
| Fenced code blocks | Yes | Report code snippets |
| Ordered and unordered lists | Yes | Section TOC, checklist items |
| Blockquotes (`>`) | Yes | ErrorCard left-border treatment |
| Tables (GFM) | Yes | MetadataCard |
| Horizontal rule (`---`) | Yes | Section dividers |
| Emoji Unicode | Yes | `✅ ❌ ⏳ ⚠️ 🔵 🟡 🔴` |
| Inline HTML | **No** | `<div>`, `<span>`, `<style>` |
| CSS injection | **No** | `<style>.msg { color: red }</style>` |
| JavaScript | **No** | `<script>alert(1)</script>` |
| Colored text | **No** | Not achievable in plain Markdown — use emoji prefixes |

#### 7.2 Chunk sizing

Report body content is yielded in 512-character chunks (configurable in Section D5, currently agreed at 512). All other content (AnalysisHeader, MetadataCard, ProgressChecklist, ErrorCard) is yielded as complete units — not chunked.

**Note:** The 512-character boundary does not align to Markdown structure (it falls mid-word, mid-sentence, or mid-table-row in most cases). OpenWebUI re-renders on each chunk. Validate that mid-chunk rendering does not produce visible artifacts in the locked OpenWebUI version during F2/F3, before changing the chunking algorithm.

#### 7.3 Keepalive yield

During the poll loop, one keepalive line is yielded every 30 seconds of elapsed polling time (per Section D4).

**F2 format (required at F2 exit):**

```
⠸ Analysis running...
```

**F3 format (after F3 UX enhancement — elapsed seconds added):**

```
⠸ Analysis running... ({elapsed}s)
```

Where `{elapsed}` is the integer number of seconds since the first yield. Elapsed-time display is an F3 UX enhancement (see `PHASE_0_ARCHITECTURE.md` Section 9 — F3 scope). F2 must NOT implement elapsed time. F3 replaces the F2 keepalive with the F3 format.

**Rationale:** OpenWebUI's HTTP client may close an idle stream after a configured timeout. Periodic yields prevent the stream from going idle. The keepalive character `⠸` (U+2838) visually suggests activity without implying false progress on specific analysis steps.

#### 7.4 Status representations

All job status representations are static text. No animated, colored, or CSS-dependent elements.

| State | Markdown text | Context |
|---|---|---|
| Submitting | `*Connecting to ArchMind backend...*` | First yield, before POST /jobs |
| Pending / Running (F2) | `⠸ Analysis running...` | Keepalive lines during poll loop |
| Pending / Running (F3) | `⠸ Analysis running... ({elapsed}s)` | F3 UX enhancement — elapsed seconds added |
| Complete | `✅ Analysis complete ({elapsed}s)` | ProgressChecklist summary on COMPLETE |
| Failed | `❌ Analysis failed` | On FAILED terminal status |

#### 7.5 Architecture pattern and severity emoji prefixes

Color differentiation is not achievable in plain Markdown. Emoji prefixes are the sole visual differentiator for architecture pattern type and finding severity.

| Category | Prefix | Example |
|---|---|---|
| Architecture: LAYERED | `🔵` | `🔵 LAYERED` |
| Architecture: MVC | `🟢` | `🟢 MVC` |
| Architecture: HEXAGONAL | `🩵` | `🩵 HEXAGONAL` |
| Architecture: SERVICE_BASED | `🟣` | `🟣 SERVICE_BASED` |
| Architecture: MONOLITH_UNDIFFERENTIATED | `⚪` | `⚪ MONOLITH_UNDIFFERENTIATED` |
| Architecture: UNKNOWN | `⚫` | `⚫ UNKNOWN` |
| Severity: CRITICAL | `🔴` | `🔴 CRITICAL` |
| Severity: HIGH | `🟠` | `🟠 HIGH` |
| Severity: MEDIUM | `🟡` | `🟡 MEDIUM` |
| Severity: LOW | `🟢` | `🟢 LOW` |

### Constraints

- No raw HTML tags in any yield.
- No `<style>` blocks, no `class=` attributes, no `id=` attributes.
- All text must be valid UTF-8.
- Do not yield empty strings (`""`). Yield `"\n"` minimum for blank lines.
- Emoji must use Unicode codepoints directly — not HTML entity form (`&#x2705;` is forbidden; `✅` is correct).

### Acceptance Criteria

- All yielded strings pass a Markdown linter with no HTML-block warnings
- No `<` or `>` characters appear in output except inside fenced code blocks (where they represent code content)
- F2: The keepalive string matches the exact format `⠸ Analysis running...` — confirmed by unit tests on `status_formatter.py`
- F3: The keepalive string matches the exact format `⠸ Analysis running... ({elapsed}s)` — confirmed by unit tests on `status_formatter.py`
- Chunked report body renders without broken tables or truncated headings in the OpenWebUI version under test — validated manually at F2/F3

---

## 8. Error Contract

### Purpose

Defines how the pipeline communicates all error conditions to the user. All user-facing errors must be yielded as formatted Markdown ErrorCards. Raw exception tracebacks must never reach the user. Internal error details are logged at WARNING or ERROR level for operator visibility.

### Requirements

#### 8.1 Error taxonomy

Six error types are defined. Each has a distinct trigger, a distinct Markdown template, and specified `job_id` availability.

| Type | Trigger | `job_id` in output? |
|---|---|---|
| `invalid_url` | URL extraction returns no valid GitHub URL from `user_message` | No — job never created |
| `job_failed` | Backend `GET /jobs/{id}` returns `status: "FAILED"` | Yes — from job creation response |
| `service_unavailable` | `POST /jobs` or `GET /jobs/{id}` returns connection refused or 5xx | No |
| `rate_limited` | 429 response from backend — `detail` field is `"Server at capacity"` | No |
| `timeout` | Poll loop duration exceeds `MAX_POLL_DURATION_SECONDS` | Yes — from job creation response |
| `repo_too_large` | 422 response from backend after M16.3 deployment | No — available after M16.3 only |

**Distinguishing `rate_limited` from `invalid_url` 422:** The backend returns 422 for both an invalid URL (Pydantic validation) and potentially for future repo-size limits (M16.3). Distinguish by the `detail` field content:
- 422 with `detail` containing a list (Pydantic format) → `invalid_url` or validation error
- 429 with `detail: "Server at capacity"` → `rate_limited`

#### 8.2 Soft errors vs hard errors

| Type | Definition | Pipeline action |
|---|---|---|
| **Soft error** | An expected, recoverable failure condition | Yield an ErrorCard and return from `pipe()` cleanly |
| **Hard error** | An unhandled exception that escapes `pipe()` | Must not happen — all code paths must be wrapped. If it does, OpenWebUI surfaces raw exception text to the user. |

All 6 error types above are soft errors. The pipeline must yield their corresponding ErrorCards and return cleanly.

#### 8.3 ErrorCard format requirements

Every ErrorCard must:
- Use a Markdown blockquote (`>`) for visual left-border treatment
- Open with `❌ **[Error Title]**`
- Include `**Repository:** owner/repo` when the repo was identified
- Include `**Job ID:** \`{id}\`` when a job was created
- Include a plain-text error description
- Include at least one actionable next step
- Close with a prompt for the user's next action

No CSS, no HTML, no inline styles.

#### 8.4 Configuration error (unconfigured Valve)

If `ARCHMIND_API_KEY` is empty when `pipe()` is called, the pipeline must yield a configuration error immediately — before any HTTP call — and return.

```
Configuration error output (specification):
  ❌ **Pipeline Not Configured**

  The ArchMind API key is not set.
  An administrator must enter the API key in the pipeline Valves settings.
```

### Constraints

- `ARCHMIND_API_KEY` must never appear in any error output yielded to the user.
- Backend error details (e.g., stack traces from the backend's 5xx response body) must not be forwarded to the user verbatim. Log them internally; show a generic `service_unavailable` ErrorCard.
- `job_failed` ErrorCard must include the `error_message` field from the `JobStatusResponse` body — this is the backend's analysis failure reason, not a system error, and is safe to surface.

### Acceptance Criteria

- Submitting a non-GitHub URL yields the `invalid_url` ErrorCard with no traceback
- Submitting a URL for a non-existent repository (causing FAILED status) yields `job_failed` with the Job ID
- Stopping the backend mid-analysis yields `service_unavailable`
- Waiting longer than `MAX_POLL_DURATION_SECONDS` yields `timeout` with the Job ID
- Empty `ARCHMIND_API_KEY` in Valves yields the configuration error before any HTTP call is made
- No unhandled exception escapes `pipe()` under any of the above conditions — confirmed by integration tests

---

## 9. Timeout Behavior

### Purpose

Defines all timeout thresholds, their sources, and the pipeline's response when each threshold is exceeded. Three independent timeout layers exist in the system.

### Requirements

#### 9.1 Timeout layers

| Layer | Owner | Default | Configurable? | Pipeline action on expiry |
|---|---|---|---|---|
| OpenWebUI stream read timeout | OpenWebUI (client-side) | **⚠ VERIFY AT F1** | Via OpenWebUI config | Connection closed by client — pipeline generator may be abandoned mid-yield |
| HTTP client request timeout | `archmind_client.py` | 30 seconds per request | Via code constant | `httpx.TimeoutException` → catch → yield `service_unavailable` ErrorCard |
| Pipeline poll hard timeout | `archmind_pipeline.py` | `MAX_POLL_DURATION_SECONDS` (1800s) | Via Valves | Yield `timeout` ErrorCard, return from `pipe()` |

#### 9.2 OpenWebUI stream timeout

OpenWebUI's browser client has a configured read timeout for streaming responses. If the pipeline does not yield any data for longer than this timeout, the client closes the connection.

**Mitigation:** The keepalive yield (Section 7.3) must occur at least every 30 seconds. `MAX_POLL_DURATION_SECONDS` is 1800 seconds — the poll loop runs for up to 360 cycles at 5-second intervals, with a keepalive yield every 6 cycles. This maintains an active stream.

**⚠ VERIFY AT F1:** The OpenWebUI stream read timeout value. If the default is less than 30 seconds, the keepalive interval must be reduced.

#### 9.3 HTTP client timeout

Each HTTP call made by `archmind_client.py` must have an explicit timeout. Calls that block indefinitely prevent the poll loop from advancing and cause the OpenWebUI stream timeout to trigger.

| HTTP call | Recommended timeout |
|---|---|
| `GET /api/v1/health` | 10 seconds |
| `POST /api/v1/jobs` | 30 seconds |
| `GET /api/v1/jobs/{job_id}` | 10 seconds |
| `GET /api/v1/reports/{report_id}` | 60 seconds (report response may be large) |

#### 9.4 Poll hard timeout sequence

```
Poll loop begins at T=0
Every POLL_INTERVAL_SECONDS: call GET /jobs/{id}, yield keepalive
At T = MAX_POLL_DURATION_SECONDS:
  → Yield timeout ErrorCard (with Job ID)
  → Log WARNING: "Poll timeout after {elapsed}s for job {job_id}"
  → Return from pipe()
  → Job may still be running on the backend
```

The `timeout` ErrorCard must include the Job ID so the operator can check backend status manually.

### Constraints

- The poll loop must check elapsed time against `MAX_POLL_DURATION_SECONDS` before each poll cycle, not after — to avoid one extra HTTP call past the deadline.
- The HTTP client timeout must be shorter than `POLL_INTERVAL_SECONDS` to prevent a hanging HTTP call from doubling the effective poll interval.
- The pipeline must not silently swallow `httpx.TimeoutException` — it must be caught and converted to a `service_unavailable` ErrorCard.

### Acceptance Criteria

- Setting `MAX_POLL_DURATION_SECONDS = 10` in Valves and waiting causes `timeout` ErrorCard to appear after ≤ 15 seconds (one poll cycle after deadline)
- An HTTP call that takes >30 seconds is cancelled and surfaces as `service_unavailable`, not an unhandled `TimeoutException`
- Keepalive yields appear at least once every 30 seconds during a running analysis — confirmed by timing the OpenWebUI response stream
- **⚠ VERIFY AT F1:** OpenWebUI stream read timeout is confirmed to be ≥ 60 seconds (or keepalive interval is adjusted accordingly)

---

## 10. Retry Behavior

### Purpose

Defines which error conditions trigger automatic retry within `pipe()`, how many retries are attempted, and the backoff strategy. Retries must be bounded — infinite retry loops are forbidden.

### Requirements

#### 10.1 Retryable conditions

| Condition | HTTP status / Exception | Retry? | Max retries | Notes |
|---|---|---|---|---|
| Transient 5xx (backend error) | 500, 502, 503, 504 | Yes | 2 | Wait `POLL_INTERVAL_SECONDS` between retries |
| Connection refused / network error | `httpx.ConnectError` | Yes | 2 | Backend may be briefly restarting |
| HTTP read timeout | `httpx.ReadTimeout` | Yes | 1 | One retry with doubled timeout |
| 401 Unauthorized | 401 | **No** | 0 | Indicates wrong API key — retrying won't help. Yield `service_unavailable` with a note to check Valve configuration. |
| 404 Not Found (job/report) | 404 | **No** | 0 | Job or report does not exist — yield `job_failed` |
| 422 Unprocessable Entity | 422 | **No** | 0 | Invalid request — retrying the same request won't succeed |
| 429 Too Many Requests | 429 | **No** | 0 | Server at capacity — yield `rate_limited` ErrorCard immediately |
| Poll `COMPLETE` not received | Poll timeout | **No** | 0 | Hard timeout reached — yield `timeout` ErrorCard |

#### 10.2 Retry scope

Retries apply only to individual HTTP calls within `archmind_client.py`. The poll loop itself is not a retry mechanism — it is a polling mechanism. Do not conflate:
- **Retry:** Re-issue the same HTTP call after a transient failure (max 2 times)
- **Poll:** Repeatedly call `GET /jobs/{id}` waiting for a terminal state (up to `MAX_POLL_DURATION_SECONDS`)

#### 10.3 Backoff strategy

| Attempt | Wait before retry |
|---|---|
| First retry | `POLL_INTERVAL_SECONDS` seconds (5s default) |
| Second retry | `POLL_INTERVAL_SECONDS × 2` seconds (10s default) |
| After second retry fails | Yield `service_unavailable` ErrorCard, return |

No exponential backoff beyond 2× — the total retry delay must be short enough that the OpenWebUI stream does not timeout while retrying.

### Constraints

- Retry logic must not mask 401 errors. A 401 on any HTTP call must surface immediately — it indicates a Valve misconfiguration.
- Retry delay must not exceed the OpenWebUI stream read timeout (see Section 9).
- All retry attempts must be logged at DEBUG level: `"Retrying {method} {url} after {status}, attempt {n}/2"`.

### Acceptance Criteria

- A backend that returns 503 twice then 202 causes the pipeline to successfully submit the job (confirmed by integration test with mock backend)
- A backend that returns 503 three times causes a `service_unavailable` ErrorCard after 2 retries
- A 401 response immediately surfaces as a configuration error (no retry)
- A 429 response immediately surfaces as `rate_limited` (no retry)
- All retry attempts are logged at DEBUG level — confirmed by test log output

---

## 11. Logging Requirements

### Purpose

Defines what the pipeline must log, at what severity level, and what it must never log. Structured logging enables operator debugging without exposing secrets.

### Requirements

#### 11.1 Required log events

| Event | Level | Fields |
|---|---|---|
| Pipeline startup (`on_startup()`) | INFO | `pipeline_version`, `api_url` (host only, no key) |
| Valves updated | INFO | `api_url` (host only), `poll_interval`, `max_poll_duration` |
| `pipe()` called | DEBUG | `conversation_id` (if available), `user_message_length` |
| URL extraction result | DEBUG | `extracted_url` or `extraction_failed: true` |
| `POST /jobs` success | INFO | `job_id`, `repo_url`, `elapsed_ms` |
| `POST /jobs` failure | WARNING | `status_code`, `detail`, `elapsed_ms` |
| Poll cycle | DEBUG | `job_id`, `status`, `elapsed_s`, `poll_count` |
| Job COMPLETE | INFO | `job_id`, `report_id`, `elapsed_s` |
| Job FAILED | WARNING | `job_id`, `error_message`, `elapsed_s` |
| Poll timeout | WARNING | `job_id`, `elapsed_s`, `max_poll_duration` |
| HTTP retry | DEBUG | `method`, `url_path`, `status_code`, `attempt` |
| `service_unavailable` | ERROR | `endpoint`, `status_code`, `elapsed_ms` |
| Unhandled exception in `pipe()` | ERROR | `exception_type`, `exception_message`, traceback |

#### 11.2 Forbidden log content

The following must **never** appear in log output at any level:

| Forbidden | Reason |
|---|---|
| `ARCHMIND_API_KEY` value | Secret — would expose authentication credential in log files |
| Full `ARCHMIND_API_URL` with embedded credentials | URL must not contain credentials |
| `X-API-Key` header value from HTTP requests | Same as above |
| Full `ReportResponse.markdown_content` | Report content may be large and confidential |

When logging the API URL, log only the host portion (scheme + hostname + port, no path, no query string).

#### 11.3 Log format

The Pipelines server may have its own log format. The pipeline's log statements must use Python's `logging` module (not `print()`). Log records must include at minimum: timestamp, level, logger name, message.

### Constraints

- Logging must be non-blocking — log calls must not add observable latency to `pipe()` execution.
- Log level must be configurable without code changes. Use the standard Python logging hierarchy.
- Debug-level logs (poll cycles, HTTP retries) must be off by default in production — only enabled when the operator sets `LOG_LEVEL=DEBUG`.

### Acceptance Criteria

- A complete analysis (submit → poll → COMPLETE) produces: 1 POST success log, ≥1 poll DEBUG log, 1 COMPLETE INFO log
- `ARCHMIND_API_KEY` does not appear in logs at any log level — confirmed by grepping test log output
- Setting `LOG_LEVEL=DEBUG` shows per-poll-cycle logs — confirmed in a dev environment
- An unhandled exception (simulated in tests) produces an ERROR log with the exception type and message

---

## 12. Performance Expectations

### Purpose

Defines the latency and throughput expectations for the pipeline's observable behavior. These are not hard SLAs but target thresholds for a healthy pipeline at v1.0.

### Requirements

#### 12.1 Latency targets

| Metric | Target | Measurement point |
|---|---|---|
| First yield latency | < 200ms | Time from `pipe()` called to first `yield` (AnalysisHeader Phase 1) |
| Job submission latency | < 2 seconds | Time from first yield to AnalysisHeader Phase 2 yield (POST /jobs round-trip) |
| Poll cycle overhead | < 100ms per cycle | Time spent in pipeline code per poll iteration, excluding the HTTP wait |
| Report rendering | < 3 seconds | Time from COMPLETE detection to first MetadataCard yield |
| Stream close | Immediate on completion | Generator returns within one event loop tick after final yield |

#### 12.2 Memory target

| Metric | Target |
|---|---|
| Memory per active `pipe()` call | < 50MB peak |
| Report body buffer | Not buffered in full — streamed in 512-char chunks. Peak buffer = max(512 chars, one `GET /reports` response) |

**The report response from `GET /reports/{id}` is loaded into memory once.** For large repositories, the full `markdown_content` field may be several hundred kilobytes. The pipeline streams it in chunks but must hold the full response in memory while chunking. This is acceptable at v1.0 concurrency levels (`MAX_CONCURRENT_JOBS = 4`).

#### 12.3 Concurrency

At v1.0, the ArchMind backend limits concurrent analyses to `MAX_CONCURRENT_JOBS = 4`. The Pipelines server may handle more than 4 simultaneous `pipe()` calls if users submit jobs in rapid succession — excess submissions beyond backend capacity receive a `rate_limited` ErrorCard immediately and do not hold resources.

### Constraints

- The pipeline must not buffer the full report response in memory repeatedly — read once, chunk once, yield, discard.
- `pipe()` must be `async` — blocking I/O calls (e.g., `httpx` requests) must use `await`, not blocking sync calls, to avoid blocking the Pipelines server's event loop.
- First yield must not depend on any I/O — it must be computed from `user_message` alone (URL extraction result).

### Acceptance Criteria

- First yield observed in OpenWebUI within 200ms of submitting a message — measured by browser DevTools network timing
- A 10MB report body (hypothetical) is streamed in chunks without causing a memory spike above 100MB in the pipeline process
- Submitting a message to a pipeline executing another `pipe()` call does not cause observable latency increase on the first yield of the new call

---

## 13. Version Compatibility

### Purpose

Locks the exact software versions that the pipeline is written against. Version mismatches between the pipeline code and the deployed OpenWebUI or Pipelines server are one of the most common integration failures.

### Requirements

#### 13.1 Compatibility matrix

**⚠ All rows marked VERIFY must be confirmed and the values filled in at F1 before F2 implementation begins.**

| Component | Required version | Source of truth | Status |
|---|---|---|---|
| OpenWebUI | **⚠ VERIFY — fill at F1** | `frontend/deployment/docker-compose.yml` | OPEN |
| OpenWebUI Pipelines server | **⚠ VERIFY — fill at F1** | `frontend/deployment/docker-compose.yml` | OPEN |
| Python (pipeline runtime) | ≥ 3.11 | Pipelines server base image | **⚠ VERIFY at F1** |
| `pydantic` | ≥ 2.0 (V2) | `frontend/pipelines/requirements.txt` | OPEN |
| `httpx` | ≥ 0.27 | `frontend/pipelines/requirements.txt` | OPEN |
| `pytest` | ≥ 8.0 | `frontend/pipelines/requirements.txt` | OPEN |
| `pytest-asyncio` | ≥ 0.23 | `frontend/pipelines/requirements.txt` | OPEN |
| `respx` | ≥ 0.21 | `frontend/pipelines/requirements.txt` | OPEN |

#### 13.2 OpenWebUI Pipelines protocol version

The Pipelines protocol defines the `pipe()` method signature, supported return types, and Valves mechanism. This protocol is not independently versioned — it is tied to the OpenWebUI Pipelines server version.

Key protocol characteristics to confirm at F1:

| Characteristic | VERIFY at F1 |
|---|---|
| `pipe()` parameter names | `user_message`, `model_id`, `messages`, `body` — confirm exact names and order |
| `AsyncGenerator` return type supported | Yes/No |
| `Valves(BaseModel)` pattern supported | Yes/No |
| `type` class attribute required | Yes/No — and required value |
| `conversation_id` in `body` dict | Key name, presence, and format |
| `WEBUI_LOGO` env var name | Exact name |
| `WEBUI_FAVICON_URL` env var name | Exact name |
| Conversation title setting mechanism | Method/attribute/auto-name |
| `str` Valve fields masked in admin | Yes/No |
| Pipeline object lifecycle | Singleton/Per-request |

#### 13.3 Version lock procedure

1. Decide the OpenWebUI version (I2 — project owner decision).
2. Pull the corresponding Docker image: `docker pull ghcr.io/open-webui/open-webui:{version}`.
3. Pull the corresponding Pipelines image: `docker pull ghcr.io/open-webui/pipelines:{version}`.
4. Commit both exact image tags to `frontend/deployment/docker-compose.yml`.
5. Verify all items in Section 13.2 against the running instance.
6. Fill all `OPEN` rows in Section 13.1 with confirmed versions.
7. Update `frontend/pipelines/requirements.txt` with confirmed package versions.

### Constraints

- `latest` image tags are forbidden in `docker-compose.yml`. Only pinned version tags are acceptable.
- If a newer OpenWebUI version is adopted mid-project, re-verify all items in Section 13.2 before proceeding.
- `requirements.txt` versions must be pinned (e.g., `httpx==0.27.2`, not `httpx>=0.27`).

### Acceptance Criteria

- All rows in Section 13.1 are filled with confirmed versions
- `docker-compose.yml` contains no `latest` tags
- `requirements.txt` contains pinned versions for all dependencies
- All Section 13.2 items are answered with confirmed values

---

## 14. Testing Requirements

### Purpose

Defines the mandatory test coverage for the pipeline, what each test file must cover, the mock strategy, and the minimum coverage threshold before F4 exit.

### Requirements

#### 14.1 Test inventory

| Test file | Milestone | Scope | Mock strategy |
|---|---|---|---|
| `test_url_extractor.py` | F2 | URL extraction and validation logic | No mocks needed — pure function |
| `test_status_formatter.py` | F2 | ProgressChecklist Markdown output | No mocks needed — pure function |
| `test_report_formatter.py` | F2 | MetadataCard, TOC, body chunking | No mocks needed — pure function |
| `test_archmind_client.py` | F4 | HTTP client — all 5 endpoints, all error codes | `respx` mocking `httpx` calls |
| `test_pipeline_integration.py` | F4 | Full `pipe()` execution | `respx` mocking backend; no live network |

#### 14.2 Required test cases per file

**`test_url_extractor.py`**
- Valid URL: `https://github.com/owner/repo` → extracts `owner/repo`
- Valid URL with `.git` suffix → strips suffix, extracts `owner/repo`
- URL embedded in sentence → correctly extracted
- Non-GitHub URL (gitlab.com, bitbucket.org) → rejected
- `http://` instead of `https://` → rejected
- Empty string → returns `None` or raises defined error
- Whitespace-only string → same as empty
- Multiple URLs in one message → first valid GitHub URL extracted

**`test_status_formatter.py`**
- `job_submitted=True, is_running=False, is_complete=False` → correct Markdown with `✅` on first item
- `job_submitted=True, is_running=True, is_complete=False` → all non-submitted items show `⏳`
- `job_submitted=True, is_running=False, is_complete=True, elapsed_seconds=47` → summary line `✅ Analysis complete (47s)`
- All checklist items present in correct order

**`test_report_formatter.py`**
- MetadataCard with all fields populated → correct table Markdown
- MetadataCard with `highest_severity_finding=None` → no crash, field omitted or shows `—`
- TOC from `sections[]` → ordered list matching `section_order`
- Empty `sections[]` → no TOC rendered (or empty TOC gracefully)
- Body chunk of < 512 chars → yielded as single chunk
- Body chunk of > 512 chars → chunked at 512-char boundaries

**`test_archmind_client.py`**
- `POST /jobs` 202 → returns `job_id`
- `POST /jobs` 401 → raises or returns defined error type
- `POST /jobs` 422 → raises or returns defined error type
- `POST /jobs` 429 → raises or returns defined error type
- `POST /jobs` 503 (then 202 on retry) → succeeds after retry
- `POST /jobs` 503 three times → raises defined error type after 2 retries
- `GET /jobs/{id}` 200 COMPLETE → returns `JobStatusResponse` with `report_id`
- `GET /jobs/{id}` 200 FAILED → returns `JobStatusResponse` with `error_message`
- `GET /jobs/{id}` 404 → raises or returns defined error type
- `GET /api/v1/health` → returns `HealthResponse`
- `GET /reports/{id}` 200 → returns `ReportResponse`
- `GET /reports/{id}` 404 → raises or returns defined error type
- Connection refused → raises or returns defined error type
- Request timeout → raises or returns defined error type

**`test_pipeline_integration.py`**
- Valid URL → PENDING → RUNNING → COMPLETE path → full yield sequence produced
- Valid URL → PENDING → FAILED path → `job_failed` ErrorCard yielded
- Invalid URL → `invalid_url` ErrorCard yielded before any HTTP call
- Backend 5xx on `POST /jobs` → `service_unavailable` ErrorCard
- Backend 429 on `POST /jobs` → `rate_limited` ErrorCard
- Poll hard timeout → `timeout` ErrorCard with Job ID
- Empty `ARCHMIND_API_KEY` → configuration error card yielded
- `highest_severity_finding=None` in report → no crash

#### 14.3 Coverage requirements

| Module | Minimum line coverage |
|---|---|
| `url_extractor.py` | 80% |
| `status_formatter.py` | 80% |
| `report_formatter.py` | 80% |
| `archmind_client.py` | 75% (some HTTP paths require network) |
| `archmind_pipeline.py` | 70% (integration tests cover main paths) |

Coverage is measured with `pytest-cov`. Report generated at: `cd frontend && python -m pytest tests/ --cov=pipelines --cov-report=term-missing`.

#### 14.4 Test runner

```
Working directory:  frontend/
Command:            python -m pytest tests/
With coverage:      python -m pytest tests/ --cov=pipelines --cov-report=term-missing
Single file:        python -m pytest tests/test_url_extractor.py -v
```

`pytest-asyncio` mode must be set to `auto` in `pytest.ini` or `pyproject.toml`:

```
[pytest]
asyncio_mode = auto
```

Without this setting, async test functions are collected but not executed, producing false-passing results.

### Constraints

- No test may make a real HTTP call to the ArchMind backend, GitHub API, or any external service. All network calls must be intercepted by `respx`.
- Tests must be runnable with no external services running (no backend, no Qdrant, no Docker).
- The `test_pipeline_integration.py` integration tests may invoke `pipe()` but must mock all HTTP calls.

### Acceptance Criteria

- `python -m pytest tests/` exits 0 with all tests passing before F4 is marked complete
- Coverage report shows ≥ 80% on `url_extractor.py`, `status_formatter.py`, `report_formatter.py`
- No test makes a real network call — confirmed by running tests with network disabled (`--no-header` or with DNS blocked)
- `asyncio_mode = auto` is configured — confirmed by running a single async test and verifying it executes (not just collected)

---

## Appendix A: Open Verification Items

All items below must be confirmed against the running OpenWebUI deployment at F1. Fill in confirmed values before F2 implementation begins.

| Item | Ref | Status | Confirmed value |
|---|---|---|---|
| OpenWebUI image version | C1, §13.1 | OPEN | |
| Pipelines image version | C2, §13.1 | OPEN | |
| `pipe()` exact parameter names and order | C3, §2.1 | OPEN | |
| `Valves(BaseModel)` supported | C4, §3 | OPEN | |
| `AsyncGenerator` return type supported | C5, §6.1 | OPEN | |
| `type` class attribute required | §1 | OPEN | |
| `WEBUI_LOGO` env var name | C6, §13.2 | OPEN | |
| `WEBUI_FAVICON_URL` env var name | C7, §13.2 | OPEN | |
| Conversation title setting mechanism | C8, §4 | OPEN | |
| `str` Valve fields render as password input | §3 | OPEN | |
| Pipeline object lifecycle (singleton/per-request) | §4.1 | OPEN | |
| `conversation_id` key in `body` dict | §5.4 | OPEN | |
| OpenWebUI stream read timeout value | §9.2 | OPEN | |
| `on_startup()` sync vs async requirement | §2.2 | OPEN | |
| Hot-reload interrupt vs drain behavior | §4.3 | OPEN | |
| Python version in Pipelines base image | §13.1 | OPEN | |

---

## Appendix B: Related Documents

| Document | Location | Relationship |
|---|---|---|
| ArchMind Backend API Contract | `frontend/docs/ARCHMIND_API_CONTRACT.md` | Backend endpoints consumed by `archmind_client.py` |
| Phase 0 Architecture | `frontend/docs/PHASE_0_ARCHITECTURE.md` | Component inventory (Part 7), Roadmap (Part 9), Checklist (Part 10) |
| Sample pipeline outputs | `frontend/examples/` | Reference Markdown for ErrorCard and report formatting |
| Deployment Guide | `frontend/docs/DEPLOYMENT_GUIDE.md` | How to run OpenWebUI + Pipelines — F5 milestone |
