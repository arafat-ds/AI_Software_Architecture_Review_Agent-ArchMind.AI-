# ArchMind AI — Frontend Phase 0: Architecture & Design

**Document Type**: Architecture Decision Document + UX Design Specification  
**Phase**: Frontend Phase 0 (Design Lock)  
**Status**: Complete
**Scope**: All frontend architectural decisions, UX design, wireframes, and implementation readiness

---

## Table of Contents

1. [Frontend Architecture Decision Document (ADD)](#1-frontend-architecture-decision-document)
2. [Complete User Journey](#2-complete-user-journey)
3. [Information Architecture](#3-information-architecture)
4. [Screen-by-Screen Wireframes](#4-screen-by-screen-wireframes)
5. [UX Decisions](#5-ux-decisions)
6. [Branding Guide](#6-branding-guide)
7. [Component Inventory](#7-component-inventory)
8. [Frontend Folder Architecture](#8-frontend-folder-architecture)
9. [Frontend Roadmap Review](#9-frontend-roadmap-review)
10. [Implementation Readiness Checklist](#10-implementation-readiness-checklist)

---

---

## 1. Frontend Architecture Decision Document

### ADR Reference Format

Each decision follows this structure:

```
ADR-FXXX: Decision Title
  Context    — What problem triggered this decision
  Decision   — What was chosen
  Considered — What alternatives were evaluated
  Pros       — Why this choice is correct
  Cons       — What is accepted as a tradeoff
  Future     — How this decision enables or constrains evolution
```

---

### ADR-F001: OpenWebUI as the Frontend Shell

**Context**

ArchMind AI requires a web UI that can: (a) accept GitHub repository URLs from users, (b) display long Markdown analysis reports with code blocks and tables, (c) persist analysis history per user, (d) handle multi-user access, (e) authenticate users, and (f) render progressive streaming output while a 30–120 second background job runs. Building all of this from scratch is Phase 11 in the original roadmap and was estimated as the largest remaining phase by scope.

The original roadmap suggested Next.js 14+ with Tailwind. Before implementation began, the project vision was clarified: OpenWebUI should be used as the frontend experience.

**Decision**

Use OpenWebUI (open-source, `ghcr.io/open-webui/open-webui:main`) as the primary browser interface for ArchMind AI.

**Alternatives Considered**

| Alternative | Why Rejected |
|---|---|
| Next.js 14 (App Router) + Tailwind | 6–8 weeks of custom UI engineering. Markdown renderer, streaming display, auth, history, responsive layout all custom-built. High quality but high cost. |
| Streamlit | Python-native, fast to prototype, but poor UX for production: page reload model, no real-time streaming, no multi-user auth, not designed for chat-style flows. |
| Gradio | Similar to Streamlit. Chat interface exists but is too simplistic for a report viewer with structured metadata, tables, and deep Markdown hierarchy. |
| Vue.js SPA | Same scope as Next.js. No advantage over Next.js for this use case; larger custom surface area than OpenWebUI. |
| Custom FastAPI Jinja2 templates | No component ecosystem, no streaming support, severe UX limitations. Appropriate for admin tools only. |

**Pros**

- Native Markdown rendering: headings, code blocks with syntax highlighting, tables, lists — all handled without a single line of custom rendering code
- Streaming response display built-in: token-by-token typewriter rendering matches what the pipeline produces
- Conversation history with search, pinning, and share links — zero backend work required
- Full authentication system: local accounts, password management, admin panel, user management
- Mobile-responsive layout tested to 320px — no custom CSS required
- Dark/light mode with system preference detection — already shipped
- Actively maintained open-source project with frequent releases
- Admin panel for pipeline management, user management, and system configuration
- Copy-to-clipboard on every message — report export works immediately
- Regenerate button — free retry/re-analysis functionality

**Cons**

- Reduced design control: UI chrome, colors, and layout are OpenWebUI's, only partially configurable via environment variables
- Upstream dependency: if OpenWebUI changes its Pipeline API interface, the ArchMind pipeline must be updated
- Chat metaphor: the interface is a chat UI, which is well-suited for ArchMind's conversational analysis model but may feel unfamiliar to users expecting a traditional dashboard
- OpenWebUI's own database (SQLite or Postgres) stores conversation history separately from ArchMind's Supabase — dual data stores

**Future Impact**

- Multi-user auth expansion: OpenWebUI already supports LDAP and OAuth2 — enabling these requires zero backend changes
- Team workspaces: OpenWebUI's group model maps to future team workspace feature
- Custom pages: OpenWebUI supports custom tool/function additions — an interactive report viewer page can be added later without replacing the shell
- If ArchMind outgrows OpenWebUI (e.g., requires complex custom dashboards), OpenWebUI can be replaced with a custom React app without any backend changes — the pipeline interface is the only coupling point

---

### ADR-F002: OpenWebUI Pipelines as the Integration Layer

**Context**

OpenWebUI is designed to talk to LLMs (OpenAI, Ollama, etc.). ArchMind AI is not an LLM — it is a FastAPI backend with a job submission + polling API. A bridge is required between what OpenWebUI expects (a streaming text response to a user message) and what ArchMind provides (an async job + polling endpoint pair).

**Decision**

Use OpenWebUI Pipelines: a separate Python server (`ghcr.io/open-webui/pipelines:main`, port 9099) that OpenWebUI treats as an OpenAI-compatible model provider. A custom Python class (`ArchMindPipeline`) intercepts user messages, executes the full ArchMind job lifecycle, and streams the result back to OpenWebUI as a token stream.

**Alternatives Considered**

| Alternative | Why Rejected |
|---|---|
| Add `/v1/chat/completions` endpoint to FastAPI | Pollutes the backend with frontend concerns. Backend is a clean analysis API — it must not know about OpenAI chat protocols. Violates separation of concerns. Regression risk on 417 passing tests. |
| LiteLLM proxy | LiteLLM proxies LLM providers. ArchMind is not an LLM. LiteLLM cannot bridge a job submission API. |
| OpenWebUI Tools (function calling) | Tools execute inside the LLM reasoning loop. ArchMind has no LLM to reason with — it IS the analysis engine. Tools require an underlying model to orchestrate them. |
| Custom WebSocket bridge server | Additional engineering scope equivalent to writing a pipeline manually. No framework support, more failure modes, no admin UI integration. |
| Direct FastAPI CORS + browser JS | Would expose the API key to the browser. Security violation. The `X-API-Key` must never appear in browser-side JavaScript. |

**Pros**

- Clean separation: pipeline is entirely responsible for the OpenWebUI ↔ ArchMind bridge
- Python: matches the team's existing language; no new language toolchain
- Hot-reloadable: pipeline code can be updated without restarting OpenWebUI
- Valves (pipeline settings) exposed in OpenWebUI admin UI — no config file editing for operators
- Streaming interface: pipeline yields chunks that OpenWebUI renders in real-time
- Independent test surface: pipeline Python code is unit-testable independently of both OpenWebUI and the ArchMind backend
- API key isolation: `ARCHMIND_API_KEY` lives in the pipeline server environment, never in the browser

**Cons**

- Additional service: 3 services (backend + openwebui + pipelines) instead of 2
- Pipelines API is OpenWebUI-specific: the pipeline code cannot be trivially reused outside of OpenWebUI
- Polling overhead: pipeline makes HTTP requests to backend every 5 seconds during job execution

**Future Impact**

- When backend adds SSE (v1.1): replace the poll loop inside the pipeline with an SSE subscription — pipeline interface to OpenWebUI is unchanged
- When backend adds WebSocket: replace poll loop with WebSocket listener — pipeline interface unchanged
- Pre-processing additions (content moderation, URL allowlisting, rate-limit per user): add to pipeline without backend changes
- Multi-pipeline support: second pipeline for "quick health check" or "list past reports" can be added to OpenWebUI separately

---

### ADR-F003: FastAPI Backend Remains Completely Unchanged Through F1–F4

**Context**

The backend has 417 passing tests, a defined API surface, and production-ready implementation. Any modification to the backend for frontend purposes introduces regression risk and blurs the architectural boundary between backend and frontend layers.

**Decision**

No modifications to the FastAPI backend, its schemas, its routers, or its security layer are required or permitted for Frontend Phases F1 through F4. The pipeline adapts to the existing API contract.

**Alternatives Considered**

| Alternative | Why Rejected |
|---|---|
| Add `GET /api/v1/jobs/{id}/events` SSE endpoint | Changes backend to serve frontend concerns. Deferred to v1.1 where it has architectural justification. |
| Add `/api/v1/reports/{id}/sections` endpoint for section-by-section retrieval | Unnecessary. `markdown_content` in the existing ReportResponse is sufficient. |
| Add `PATCH /api/v1/jobs/{id}/cancel` in Phase F | This is backend roadmap M16.2. It should be done in the backend roadmap, not as a frontend dependency. |

**Pros**

- Zero regression risk to 417 passing tests
- Backend-frontend boundary is clean and unambiguous
- Backend can evolve independently of frontend timeline

**Cons**

- Pipeline must implement its own polling logic rather than receiving push notifications

**Future Impact**

- Phase F5 may require CORS origins update to include production OpenWebUI domain — this is a config change, not a code change, and is already anticipated in `settings.cors_origins`

---

### ADR-F004: Polling Bridged Into Streaming via Progressive Markdown Chunks

**Context**

OpenWebUI renders responses using a streaming display — content appears progressively as the model generates tokens. The ArchMind backend has no streaming capability: job status is polled via `GET /api/v1/jobs/{job_id}`, and the pipeline must wait potentially 2 minutes for a job to complete.

If the pipeline blocks until job completion then returns the full report in one chunk, the user sees nothing for up to 120 seconds and then the entire report appears at once. This is unacceptable UX for a production tool.

**Decision**

The pipeline simulates streaming by yielding Markdown chunks at each poll cycle. A progress display (checklist format) is yielded immediately and updated on each poll. When the job completes, the report is yielded in small chunks (≤512 chars) to produce smooth progressive rendering. The user sees meaningful progress from second 0 to job completion.

**Poll Cycle Design:**

```
t=0s:   Yield header block (repo name, job_id, submission confirmed)
t=0s:   Yield initial checklist (all items pending)
t=5s:   Poll → RUNNING → Yield updated checklist + elapsed time
t=10s:  Poll → RUNNING → Yield keepalive chunk (prevents timeout)
...
t=Ns:   Poll → COMPLETE → Yield section divider
t=Ns:   GET /reports/{report_id}
t=Ns:   Yield metadata card
t=Ns:   Yield TOC
t=Ns:   Yield markdown_content in 512-char chunks
```

**Alternatives Considered**

| Alternative | Why Rejected |
|---|---|
| Block until complete, return full response | Unacceptable UX. 120 second blank screen. OpenWebUI may timeout the connection. |
| Fake token-by-token streaming from start | Possible but misleading — implies content is being generated when it is not. |
| Server-Sent Events on backend (v1.0) | Backend does not have SSE. Out of v1.0 scope. |

**Pros**

- User has meaningful visual feedback from the first second
- No changes to backend required
- Works within OpenWebUI's existing streaming model

**Cons**

- Not truly event-driven — polling every 5 seconds is a synthetic approximation
- Progress checklist cannot show granular node-level progress (backend does not emit node events)

**Future Impact**

- When backend adds real SSE events (v1.1): pipeline replaces poll loop with `async for event in sse_stream`. The pipeline's OpenWebUI interface (yield chunks) does not change at all.
- When backend adds Redis pub/sub for job events: pipeline subscribes to Redis channel instead of polling HTTP. Same interface change as SSE.

---

### ADR-F005: OpenWebUI Conversation History as the Report History Store

**Context**

Users need to find and re-read past analysis reports. This requires a history mechanism. Options: build a custom history page backed by the existing Supabase `jobs` and `reports` tables, or use OpenWebUI's built-in conversation history.

**Decision**

Use OpenWebUI's native conversation history as the report history mechanism at v1.0. Each analysis session is one conversation. Past analyses are accessible via the left sidebar search.

**Alternatives Considered**

| Alternative | Why Rejected |
|---|---|
| Custom history page (Supabase-backed) | Requires: frontend page component, API call to `GET /api/v1/jobs`, pagination, sorting, filtering UI. Significant scope. OpenWebUI does not natively support custom pages without a plugin system. |
| Custom OpenWebUI plugin/page | More complex than pipeline. Not documented or stable in current OpenWebUI version. |
| Report history via Pipelines (special command "list history") | Possible, but creates an inconsistent UX. History would appear as a chat message rather than a sidebar. |

**Pros**

- Zero additional engineering work
- Instant: works from day one of OpenWebUI deployment
- Built-in search by repo name (via conversation title)
- Persistent across browser sessions and devices (server-side storage)
- Share link per conversation available

**Cons**

- History is stored in OpenWebUI's database (SQLite or Postgres), not in ArchMind's Supabase — dual stores
- If OpenWebUI database is lost, history is lost (mitigated by named volume persistence)
- Cannot query history programmatically via ArchMind's API
- No custom sorting/filtering by architecture pattern, language, etc.

**Future Impact**

- v1.1: If advanced report management is required (search by finding severity, compare two analyses, team shared history), build a custom reports dashboard backed by `GET /api/v1/jobs` and `GET /api/v1/reports/{id}`. This does not conflict with OpenWebUI conversation history — both can coexist.
- v1.1: OpenWebUI conversation export feature allows bulk export of all analyses as JSON.

---

### ADR-F006: Single Shared API Key (Server-to-Server Authentication)

**Context**

Backend authentication (M9.1) uses a static `X-API-Key` header. The pipeline must present this key on every API call. The key must never be exposed to the browser (JavaScript clients cannot hold secrets). OpenWebUI's Pipelines server runs server-side only.

**Decision**

A single shared `ARCHMIND_API_KEY` is stored as an environment variable in the Pipelines server. All users' analysis requests are proxied through the pipeline using this single key. The key is a server-side secret only — never in the browser, never in OpenWebUI's client-side storage.

**Alternatives Considered**

| Alternative | Why Rejected |
|---|---|
| Per-user API keys | Requires an API key issuance, storage, and rotation system. v1.0 is a team tool with static auth. Deferred to v1.1. |
| OAuth2 tokens per OpenWebUI user | Requires backend OAuth2 server, token issuing, validation. Not in v1.0 backend roadmap. |
| Pass API key via OpenWebUI user settings | Exposes key in browser storage (localStorage). Security violation. |

**Pros**

- Matches M9.1 design intent exactly
- Key never visible in browser devtools, network tab, or JavaScript runtime
- Simple: one secret, one location (pipeline server env var)

**Cons**

- All users share backend identity — no per-user audit trail at the backend level (acceptable for v1.0 team tool)
- If the key is rotated, the pipeline must be restarted

**Future Impact**

- v1.1: When backend adds per-user JWT auth (replacing static key), pipeline extracts the OpenWebUI user session token and passes it as a Bearer token. The `Valves` configuration class in the pipeline gets a new field: `AUTH_MODE = "api_key" | "user_jwt"`. No change to OpenWebUI, no change to the pipeline's interface.

---

### ADR-F007: markdown_content as the Canonical Report Rendering Source

**Context**

The `ReportResponse` schema provides two ways to access report content: `markdown_content` (the full pre-assembled Markdown string) and `sections[]` (ordered array of `ReportSectionResponse` objects, each with `section_key`, `section_title`, `content_markdown`).

**Decision**

Use `markdown_content` as the primary rendering source. The pipeline streams it verbatim into OpenWebUI after prepending a metadata card and table of contents built from `sections[]` titles.

**Alternatives Considered**

| Alternative | Why Rejected |
|---|---|
| Iterate `sections[]` and join `content_markdown` | Produces identical output to `markdown_content`. Extra complexity for zero benefit. `markdown_content` is already the authoritative assembled version. |
| Render `sections[]` as tabbed navigation | Requires custom OpenWebUI plugin or page. Out of scope for v1.0. Can be added as an enhancement in v1.1 interactive report viewer. |
| Custom HTML builder from sections | Breaks OpenWebUI's Markdown pipeline. HTML injection in chat messages is unsupported and potentially unsafe. |

**Pros**

- Zero parsing complexity
- Exact output as designed by the report generation node
- Section order guaranteed by backend

**Cons**

- No interactive section navigation (TOC links are text-only, not scroll-anchored)

**Future Impact**

- When an interactive report viewer is built (custom OpenWebUI page, v1.1), `sections[]` becomes the primary data source for a tabbed or scrollspy-based navigation component.

---

### ADR-F008: Future Scalability — Redis, WebSocket, Multi-User

This section documents how currently deferred capabilities will integrate into the established architecture without requiring redesign.

#### Redis Integration (v1.1)

**Current state**: Analysis orchestrator uses in-process job state. Orphan recovery runs on restart.

**Future state**: When a Redis pub/sub queue is added for job events, the pipeline replaces its HTTP poll loop:

```
Current:  while True: sleep(5); GET /jobs/{id}
Future:   async for event in redis.subscribe(f"job:{job_id}:events"): yield progress_chunk
```

The pipeline's Valves class gains: `REDIS_URL: str = "redis://redis:6379"`. The OpenWebUI interface (yield chunks to browser) is completely unchanged.

#### WebSocket Integration (v1.1)

**Current state**: No WebSocket on backend.

**Future state**: If `GET /api/v1/jobs/{id}/ws` is added, the pipeline replaces the poll loop with a WebSocket client. The progressive streaming to OpenWebUI remains identical — only the data source changes.

#### Server-Sent Events Integration (v1.1)

**Current state**: No SSE on backend.

**Future state**: If `GET /api/v1/jobs/{id}/events` (SSE) is added, the pipeline subscribes with `httpx.AsyncClient.astream()`. Each SSE event maps to a pipeline yield. No interface changes.

#### Multi-User Auth Expansion (v1.1)

**Current state**: Single shared API key, all users share backend identity.

**Future state**: When backend adds per-user JWT auth:
- OpenWebUI continues to handle browser-level user authentication
- Pipeline reads the OpenWebUI user identity from the request context
- Pipeline exchanges OpenWebUI identity for a backend JWT (via a new `/auth/token` endpoint)
- Pipeline sends `Authorization: Bearer {jwt}` instead of `X-API-Key`
- OpenWebUI UI unchanged; backend gains user-level audit trails

The pipeline Valves class `AUTH_MODE` field controls which auth scheme is active. No redeployment of OpenWebUI required.

#### Team Workspaces (v2.0)

OpenWebUI natively supports organizations and shared conversations. When ArchMind gains team workspace support:
- OpenWebUI's group model maps directly to ArchMind workspaces
- Shared conversations in OpenWebUI = shared report access in ArchMind
- No custom workspace UI required

---

---

## 2. Complete User Journey

### State Diagram

```
[Not Logged In]
      │
      │ open browser
      ▼
[Login Screen]
      │
      │ valid credentials
      ▼
[Chat Interface — Empty State]
      │
      │ type/paste GitHub URL + submit
      ▼
[Chat Interface — Submission Confirmed]
      │
      │ pipeline processing (0–5s)
      ▼
[Progress Stream — Live]
      │
      │ job COMPLETE (30–120s)
      ▼
[Report Stream — Rendering]
      │
      │ report fully rendered
      ▼
[Report View — Reading]
      │
      ├── copy report  ─────────────────────→ [Clipboard]
      │
      ├── new analysis ─────────────────────→ [Chat Interface — Empty State]
      │
      ├── regenerate   ─────────────────────→ [Progress Stream — Live]
      │
      ├── open history ─────────────────────→ [History Sidebar]
      │
      └── open settings ────────────────────→ [Settings Panel]

[History Sidebar]
      │
      │ click past analysis
      ▼
[Report View — Reading] (from stored conversation)

[Settings Panel]
      │
      │ save settings
      ▼
[Chat Interface — return to last conversation]

[Admin Panel]   (admin users only)
      │
      ├── manage users
      ├── manage pipelines
      └── view pipeline logs
```

---

### Journey 1: New User — First Analysis

**Step 1.1: Landing**

User navigates to `https://archmind.yourdomain.com`. OpenWebUI serves the login page. No unauthenticated access to any feature. The page title reads "ArchMind AI". The ArchMind logo appears in the header.

**Step 1.2: Login**

User enters email and password. On success, OpenWebUI issues a session token stored in the browser (HttpOnly cookie or localStorage, OpenWebUI-managed). User is redirected to the chat interface. The model selector defaults to "ArchMind AI — Architecture Reviewer".

**Step 1.3: Chat Interface — Welcome State**

The chat area displays the system welcome message (set by pipeline system prompt):

```
ArchMind AI — Software Architecture Reviewer

Submit a GitHub repository URL to receive a comprehensive
engineering audit report.

Supported formats:
  https://github.com/owner/repository
  https://github.com/owner/repository.git

Example:
  https://github.com/pallets/flask

Type your URL in the input below and press Enter or click Analyze.
```

The left sidebar shows "New Analysis" at the top, with an empty history list below it.

**Step 1.4: Repository Submission**

User types or pastes a GitHub URL into the chat input field. The URL validates client-side (pipeline) immediately on submission. User presses Enter or clicks the submit button.

**Step 1.5: Immediate Feedback — Two-Phase Header**

The pipeline validates the URL. If valid, it yields a response in two phases.

**Phase 1 — before POST /jobs (< 200ms):** The pipeline yields the initial header immediately, before any network call:

```
## ArchMind AI — Submitting...

**Repository:** pallets/flask
```

**Phase 2 — after POST /jobs returns 202:** The confirmed Job ID is appended. The Job ID never appears before the backend confirms it:

```
**Job ID:** 3fa85f64-5717-4562-b3fc-2c963f66afa6
**Submitted:** 2026-08-03 14:32:07 UTC

---

### Pipeline Status

- [x] Job submitted ✓
- [ ] Repository ingestion
- [ ] Code parsing
- [ ] Architecture analysis
- [ ] Security analysis
- [ ] Knowledge base retrieval
- [ ] Recommendation generation
- [ ] Report composition
```

If POST /jobs fails (connection error, 5xx, 429), an ErrorCard is yielded instead of Phase 2.

**Step 1.6: Progress Phase (5s – ~120s)**

Every 5 seconds, the pipeline polls the backend. The stream yields a time update:

```
*Elapsed: 15s — Analysis running...*
```

No new checklist items can be checked (backend does not emit node-level events), but the elapsed time provides ongoing evidence that the system is working.

**Step 1.7: Job Completion (varies)**

On `COMPLETE` status detection, the pipeline immediately calls `GET /api/v1/reports/{report_id}`. The stream transitions with a visual divider:

```
- [x] Job submitted ✓
- [x] Analysis complete (47s) ✓

---

## Analysis Complete

**Repository:** pallets/flask
**Completed:** 2026-08-03 14:32:54 UTC

---
```

**Step 1.8: Metadata Card Renders**

The metadata summary table streams into the chat:

```
| Field                    | Value              |
|--------------------------|--------------------|
| Primary Language         | Python             |
| Architecture Pattern     | LAYERED            |
| Confidence               | HIGH               |
| Security Findings        | 2 (1 CRITICAL)     |
| Recommendations          | 6 (2 P1)           |
| Files Analyzed           | 89                 |
| Analysis Duration        | 47 seconds         |
| RAG Chunks Used          | 7                  |
| Total LLM Tokens         | 14,203             |
```

**Step 1.9: Table of Contents Renders**

```
### Report Contents

1. Executive Summary
2. Repository Overview
3. Architecture Assessment
4. Security Findings
5. Recommendations
6. Actionable Next Steps
```

**Step 1.10: Report Body Streams**

The full `markdown_content` streams progressively in 512-character chunks. All sections, headings, code blocks, tables, and lists render as the user reads. The user can start reading from the top while the bottom continues loading.

**Step 1.11: Report Complete**

The stream ends. The full report is stored in OpenWebUI's conversation history. The left sidebar auto-names the conversation "pallets/flask — 2026-08-03".

**Step 1.12: Post-Report Actions**

User can:
- **Read**: scroll through the report in-place
- **Copy**: click the copy icon on the message to copy full Markdown
- **Regenerate**: click regenerate to re-submit the same URL for a fresh analysis
- **New analysis**: click "+ New Analysis" in the sidebar to start a new conversation
- **Share**: use OpenWebUI's share button to get a shareable link to this report

---

### Journey 2: Returning User — Reading Past Report

**Step 2.1: Login**

Same as Journey 1.2.

**Step 2.2: History Sidebar**

Left sidebar shows recent conversations. Each entry shows the repo name and date. User clicks "django/django — 2026-08-02".

**Step 2.3: Report View**

The full conversation loads from OpenWebUI's storage. The complete report renders immediately from stored content — no backend call needed. The user reads the previously generated report.

**Step 2.4: Optional Re-analysis**

If the user wants a fresh analysis of the same repo, they click "Regenerate". The pipeline detects the last message's GitHub URL and re-submits it. A new report appears as a second message in the same conversation thread, enabling before/after comparison.

---

### Journey 3: Admin — Pipeline Management

**Step 3.1: Admin Login**

Admin logs into OpenWebUI with an admin-level account.

**Step 3.2: Admin Panel**

Navigate to `/admin`. Admin panel shows: Users, Pipelines, Settings.

**Step 3.3: Pipeline Configuration**

Admin navigates to Pipelines. The ArchMind pipeline is listed. Admin can:
- View pipeline status (connected/disconnected)
- Edit Valves (ARCHMIND_API_URL, ARCHMIND_API_KEY, poll interval)
- View pipeline logs
- Install a new pipeline version

**Step 3.4: User Management**

Admin creates new user accounts. Assigns default model (ArchMind AI). Sets account type. Disables self-registration (ENABLE_SIGNUP=false).

---

### Journey 4: Error Recovery

**Step 4.1: Invalid URL Submitted**

User types "github.com/owner/repo" (no https://). Pipeline validates immediately and streams:

```
**Input Error**

Repository URL must start with `https://github.com/`.

Your input: `github.com/owner/repo`

Correct format: `https://github.com/owner/repo`
```

**Step 4.2: Backend Unavailable**

Pipeline cannot reach `ARCHMIND_API_URL`. Stream yields the `service_unavailable` ErrorCard:

```
> ❌ **Service Unavailable**
>
> Could not connect to the ArchMind backend.
>
> The analysis service is temporarily unavailable. Try again in a few minutes.
> If the problem persists, contact your administrator.
```

Internal details (hostname, connection error message) are written to pipeline logs only — never to user-facing output.

**Step 4.3: Job Failed**

Backend returns `status: FAILED`. Pipeline streams:

```
**Analysis Failed**

The analysis of `owner/repo` encountered an error.

**Error:** Repository clone failed — repository not found or is private.

**Job ID:** 3fa85f64-5717-4562-b3fc-2c963f66afa6

Possible causes:
- The repository is private (ArchMind only analyzes public repositories)
- The repository URL is incorrect
- GitHub is temporarily unavailable

Submit a corrected URL below to try again.
```

**Step 4.4: Rate Limited**

Backend returns 429. Pipeline streams:

```
**Request Limit Reached**

The analysis server is currently at capacity or has rate-limited this request.

Please wait 60 seconds and try again.
```

---

---

## 3. Information Architecture

### Navigation Hierarchy

```
ArchMind AI
│
├── Chat (Primary Surface)
│   ├── New Analysis (creates new conversation)
│   ├── Active Conversation (progress + report)
│   └── History Item (past conversation)
│
├── Settings
│   ├── Account
│   │   ├── Profile (display name, email)
│   │   └── Password
│   ├── Interface
│   │   ├── Theme (light/dark/system)
│   │   ├── Language
│   │   └── Default Model
│   └── Notifications (if enabled)
│
├── Admin Panel  [Admin only]
│   ├── Users
│   │   ├── User List
│   │   ├── Create User
│   │   └── Edit/Delete User
│   ├── Pipelines
│   │   ├── Installed Pipelines
│   │   ├── Pipeline Valves (ArchMind config)
│   │   └── Pipeline Logs
│   └── System
│       ├── Environment Status
│       └── Version Info
│
└── Profile Menu (top right)
    ├── Settings
    ├── Admin Panel [Admin only]
    └── Logout
```

---

### Sidebar Content Specification

**What lives in the left sidebar:**

```
[Sidebar]
├── Header: "ArchMind AI" logo + collapse button
├── Action: "+ New Analysis" button (primary, always visible)
├── Search: "Search analyses..." (text input, filters history)
├── Pinned Section (if any pinned conversations)
│   └── [Pinned conversation items]
├── Recent Section: "Today"
│   └── [Conversation items — today]
├── Recent Section: "Yesterday"
│   └── [Conversation items — yesterday]
├── Recent Section: "This Week"
│   └── [Conversation items — older]
└── Footer
    ├── [Settings] link
    └── [User avatar] → Profile menu
```

**Conversation item format:**
- Primary text: repository name (e.g., "pallets/flask")
- Secondary text: date + status badge if failed
- Hover actions: pin, share, delete

---

### Header Content Specification

**What lives in the top header:**

```
[Header — Desktop]
├── Left: Hamburger menu (collapse sidebar)
├── Center: Model selector dropdown — "ArchMind AI ▼"
│          (for v1.0: only ArchMind AI available, no other models)
└── Right: [?] Help button | [User avatar] Profile menu
```

**What lives in the top header on mobile:**

```
[Header — Mobile]
├── Left: Hamburger menu (open sidebar overlay)
├── Center: "ArchMind AI" text (no model selector, fixed)
└── Right: [User avatar] Profile menu
```

---

### Chat Surface Content Specification

**What lives in the main chat area:**

```
[Chat Area]
├── Message list (scrollable)
│   ├── System welcome message (first load only)
│   ├── User message (GitHub URL, styled differently)
│   └── Pipeline response (streaming Markdown report)
├── Message actions (hover)
│   ├── Copy message
│   ├── Regenerate response
│   └── Edit message (re-submit modified URL)
└── Input area (sticky bottom)
    ├── Text input: "Enter a GitHub repository URL..."
    ├── Submit button (or Enter key)
    └── Character count / status indicators
```

---

### Settings Panel Content Specification

**Settings hierarchy:**

```
Settings
├── General
│   ├── Display Language
│   ├── Theme (System / Light / Dark)
│   ├── Notification Sound (on/off)
│   └── Enter Key Behavior (Send / New Line)
├── Account
│   ├── Display Name
│   ├── Email Address
│   └── Change Password
└── About
    ├── ArchMind Version
    ├── OpenWebUI Version
    └── Pipeline Status
```

---

### Admin Panel Content Specification

**Admin panel hierarchy:**

```
Admin Panel
├── Dashboard
│   ├── Active Users
│   ├── Total Analyses (conversation count)
│   └── Pipeline Health
├── Users
│   ├── User Table (email, name, role, created, last active)
│   ├── Create User form
│   └── Edit / Delete / Suspend user
├── Pipelines
│   ├── Installed Pipeline list
│   ├── ArchMind Pipeline Valves
│   │   ├── ARCHMIND_API_URL
│   │   ├── ARCHMIND_API_KEY
│   │   ├── POLL_INTERVAL_SECONDS
│   │   └── MAX_POLL_DURATION_SECONDS
│   └── Pipeline Logs (real-time)
└── Settings
    ├── ENABLE_SIGNUP (true/false)
    ├── DEFAULT_MODELS
    └── WEBUI_NAME
```

---

---

## 4. Screen-by-Screen Wireframes

### Wireframe Legend

```
[  ] = interactive element (button, input, link)
( ) = radio button / toggle
╔═╗ = panel/card border
─── = divider
··· = scrollable overflow
▶   = submit / action indicator
█   = filled / selected
░   = empty / placeholder
↑↓  = scroll indicator
```

---

### Screen 1: Login Page

#### Desktop (1280px)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                                                                              ║
║                           ┌──────────────────┐                              ║
║                           │  [ArchMind Logo] │                              ║
║                           │  ArchMind AI     │                              ║
║                           └──────────────────┘                              ║
║                                                                              ║
║                    ╔══════════════════════════════════╗                     ║
║                    ║                                  ║                     ║
║                    ║     Sign In to ArchMind AI       ║                     ║
║                    ║     ─────────────────────────    ║                     ║
║                    ║                                  ║                     ║
║                    ║     Email                        ║                     ║
║                    ║     [                          ] ║                     ║
║                    ║                                  ║                     ║
║                    ║     Password                     ║                     ║
║                    ║     [                          ] ║                     ║
║                    ║                                  ║                     ║
║                    ║     [      Sign In           ▶] ║                     ║
║                    ║                                  ║                     ║
║                    ║     Forgot password?             ║                     ║
║                    ║                                  ║                     ║
║                    ╚══════════════════════════════════╝                     ║
║                                                                              ║
║                    AI-powered Software Architecture Review                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

#### Tablet (768px)

```
╔══════════════════════════════════════════╗
║                                          ║
║            [ArchMind Logo]               ║
║              ArchMind AI                 ║
║                                          ║
║   ╔══════════════════════════════════╗   ║
║   ║  Sign In to ArchMind AI         ║   ║
║   ║  ──────────────────────────     ║   ║
║   ║                                 ║   ║
║   ║  Email                          ║   ║
║   ║  [                            ] ║   ║
║   ║                                 ║   ║
║   ║  Password                       ║   ║
║   ║  [                            ] ║   ║
║   ║                                 ║   ║
║   ║  [       Sign In            ▶] ║   ║
║   ║                                 ║   ║
║   ║  Forgot password?               ║   ║
║   ╚══════════════════════════════════╝   ║
║                                          ║
╚══════════════════════════════════════════╝
```

#### Mobile (375px)

```
╔══════════════════════════╗
║                          ║
║     [ArchMind Logo]      ║
║       ArchMind AI        ║
║                          ║
║  Sign In                 ║
║  ─────────────────────   ║
║                          ║
║  Email                   ║
║  [                     ] ║
║                          ║
║  Password                ║
║  [                     ] ║
║                          ║
║  [     Sign In       ▶] ║
║                          ║
║  Forgot password?        ║
║                          ║
╚══════════════════════════╝
```

---

### Screen 2: Chat Interface — Empty State (Welcome)

#### Desktop (1280px)

```
╔═══════════════╦══════════════════════════════════════════════════════════════╗
║ ☰ ArchMind AI ║  [  ArchMind AI — Architecture Reviewer  ▼  ]   [?] [A▼]   ║
╠═══════════════╬══════════════════════════════════════════════════════════════╣
║               ║                                                              ║
║ [+ New        ║                                                              ║
║   Analysis]   ║                                                              ║
║               ║                                                              ║
║ [Search ···]  ║              ⬡  ArchMind AI                                 ║
║               ║                                                              ║
║ ─── Today ─── ║        AI-powered Software Architecture Review              ║
║               ║                                                              ║
║ (empty)       ║   Submit a GitHub repository URL to receive a               ║
║               ║   comprehensive engineering audit report.                   ║
║               ║                                                              ║
║               ║   Supported format:                                          ║
║               ║   https://github.com/owner/repository                       ║
║               ║                                                              ║
║               ║   Example:                                                   ║
║               ║   https://github.com/pallets/flask                          ║
║               ║                                                              ║
║               ║                                                              ║
║               ║                                                              ║
║               ╠══════════════════════════════════════════════════════════════╣
║ [⚙ Settings]  ║  [ https://github.com/owner/repo ···················· ] [▶] ║
║ [A] Profile   ║                                                              ║
╚═══════════════╩══════════════════════════════════════════════════════════════╝
  240px           remaining width
```

#### Tablet (768px)

```
╔═══════════════════════════════════════════╗
║ ☰  ArchMind AI              [?]  [A▼]    ║
╠═══════════════════════════════════════════╣
║                                           ║
║             ⬡  ArchMind AI               ║
║                                           ║
║      AI-powered Architecture Review      ║
║                                           ║
║   Submit a GitHub URL below to begin     ║
║   your analysis.                         ║
║                                           ║
║   https://github.com/owner/repo          ║
║                                           ║
║                                           ║
╠═══════════════════════════════════════════╣
║  [ https://github.com/owner/repo ·· ] [▶]║
╚═══════════════════════════════════════════╝

[Sidebar overlay — hidden by default on tablet]
```

#### Mobile (375px)

```
╔══════════════════════════╗
║ ☰  ArchMind AI    [A▼]  ║
╠══════════════════════════╣
║                          ║
║     ⬡ ArchMind AI       ║
║                          ║
║  AI-powered Architecture ║
║  Review                  ║
║                          ║
║  Submit a GitHub URL:    ║
║  https://github.com/     ║
║  owner/repo              ║
║                          ║
║                          ║
║                          ║
╠══════════════════════════╣
║ [github.com/owner/·] [▶] ║
╚══════════════════════════╝
```

---

### Screen 3: Analysis In Progress

#### Desktop (1280px)

```
╔═══════════════╦══════════════════════════════════════════════════════════════╗
║ ☰ ArchMind AI ║  [  ArchMind AI — Architecture Reviewer  ▼  ]   [?] [A▼]   ║
╠═══════════════╬══════════════════════════════════════════════════════════════╣
║               ║                                                              ║
║ [+ New        ║  You:                                                        ║
║   Analysis]   ║  https://github.com/pallets/flask              [14:32:07]   ║
║               ║                                                              ║
║ [Search ···]  ║  ──────────────────────────────────────────────────────────  ║
║               ║                                                              ║
║ ─── Today ─── ║  ⬡ ArchMind AI                                              ║
║               ║                                                              ║
║ █ pallets/    ║  ## ArchMind AI — Submitting...                             ║
║   flask       ║                                                              ║
║   14:32       ║  **Repository:** pallets/flask                               ║
║               ║  **Job ID:** 3fa85f64-5717-4562-b3fc-2c963f66afa6           ║
║               ║                                                              ║
║               ║  ---                                                         ║
║               ║                                                              ║
║               ║  ### Pipeline Status                                         ║
║               ║                                                              ║
║               ║  - [x] Job submitted ✓                                       ║
║               ║  - [ ] Repository ingestion                                  ║
║               ║  - [ ] Code parsing                                          ║
║               ║  - [ ] Architecture analysis                                 ║
║               ║  - [ ] Security analysis          ↑                          ║
║               ║  - [ ] Knowledge base retrieval   │ streaming...             ║
║               ║  - [ ] Recommendation generation                             ║
║               ║  - [ ] Report composition                                    ║
║               ║                                                              ║
║               ║  ⠸ Analysis running...                                       ║
║               ╠══════════════════════════════════════════════════════════════╣
║ [⚙ Settings]  ║  [ Message input disabled during analysis ··············· ] ║
║ [A] Profile   ║                                                              ║
╚═══════════════╩══════════════════════════════════════════════════════════════╝
```

#### Mobile (375px)

```
╔══════════════════════════╗
║ ☰  ArchMind AI    [A▼]  ║
╠══════════════════════════╣
║  You:                    ║
║  https://github.com/     ║
║  pallets/flask  [14:32]  ║
║ ─────────────────────── ║
║  ⬡ ArchMind AI          ║
║                          ║
║  Submitting...           ║
║  pallets/flask           ║
║                          ║
║  Pipeline Status         ║
║  [x] Job submitted ✓     ║
║  [ ] Ingestion           ║
║  [ ] Code parsing        ║
║  [ ] Architecture        ║
║  [ ] Security            ║
║  [ ] RAG retrieval       ║
║  [ ] Recommendations     ║
║  [ ] Report              ║
║                          ║
║  ⠸ Analysis running...  ║
╠══════════════════════════╣
║ [Analyzing... (disabled)]║
╚══════════════════════════╝
```

---

### Screen 4: Report View

#### Desktop (1280px)

```
╔═══════════════╦══════════════════════════════════════════════════════════════╗
║ ☰ ArchMind AI ║  [  ArchMind AI — Architecture Reviewer  ▼  ]   [?] [A▼]   ║
╠═══════════════╬══════════════════════════════════════════════════════════════╣
║               ║  You:                                                        ║
║ [+ New        ║  https://github.com/pallets/flask              [14:32:07]   ║
║   Analysis]   ║                                                              ║
║               ║  ──────────────────────────────────────────────────────────  ║
║ [Search ···]  ║                                                              ║
║               ║  ⬡ ArchMind AI                              [↗] [⎘] [↺]   ║
║ ─── Today ─── ║                                                              ║
║               ║  ## Analysis Complete — pallets/flask                        ║
║ █ pallets/    ║                                                              ║
║   flask       ║  | Field                  | Value          |                 ║
║   14:32 ●     ║  |------------------------|----------------|                 ║
║               ║  | Primary Language       | Python         |                 ║
║               ║  | Architecture Pattern   | LAYERED        |                 ║
║               ║  | Confidence             | HIGH           |                 ║
║               ║  | Security Findings      | 2 (1 CRITICAL) |                 ║
║               ║  | Recommendations        | 6 (2 P1)       |                 ║
║               ║  | Files Analyzed         | 89             |                 ║
║               ║  | Duration               | 47 seconds     |                 ║
║               ║  | RAG Chunks Used        | 7              |                 ║
║               ║  | Total LLM Tokens       | 14,203         |                 ║
║               ║                                                              ║
║               ║  ---                                                         ║
║               ║                                                              ║
║               ║  ### Report Contents                                         ║
║               ║  1. Executive Summary                                        ║
║               ║  2. Repository Overview                                      ║
║               ║  3. Architecture Assessment                  ↕ scrollable    ║
║               ║  4. Security Findings                                        ║
║               ║  5. Recommendations                                          ║
║               ║  6. Actionable Next Steps                                    ║
║               ║                                                              ║
║               ║  ---                                                         ║
║               ║                                                              ║
║               ║  # Executive Summary                                         ║
║               ║  ···                                                         ║
║               ╠══════════════════════════════════════════════════════════════╣
║ [⚙ Settings]  ║  [ Enter a GitHub repository URL to analyze ·············] ║
║ [A] Profile   ║                                                              ║
╚═══════════════╩══════════════════════════════════════════════════════════════╝

[↗] = Share   [⎘] = Copy   [↺] = Regenerate
[●] = completion status indicator in sidebar
```

#### Tablet (768px)

```
╔═══════════════════════════════════════════╗
║ ☰  ArchMind AI              [?]  [A▼]    ║
╠═══════════════════════════════════════════╣
║  ⬡ ArchMind AI          [↗] [⎘] [↺]    ║
║                                           ║
║  ## Analysis Complete — pallets/flask     ║
║                                           ║
║  | Field          | Value        |        ║
║  |----------------|--------------|        ║
║  | Language       | Python       |        ║
║  | Pattern        | LAYERED      |        ║
║  | Confidence     | HIGH         |        ║
║  | Findings       | 2 (1 CRIT.)  |        ║
║  | Recommendations| 6 (2 P1)     |        ║
║  | Duration       | 47s          |        ║
║                                           ║
║  Report Contents                          ║
║  1. Executive Summary                     ║
║  2. Repository Overview                   ║
║  3. Architecture Assessment          ↕   ║
║  4. Security Findings                     ║
║  5. Recommendations                       ║
║  6. Actionable Next Steps                 ║
║                                           ║
║  # Executive Summary                      ║
║  ···                                      ║
╠═══════════════════════════════════════════╣
║  [ Enter a GitHub URL to analyze ·· ] [▶]║
╚═══════════════════════════════════════════╝
```

#### Mobile (375px)

```
╔══════════════════════════╗
║ ☰  ArchMind AI    [A▼]  ║
╠══════════════════════════╣
║ ⬡  [⎘] [↺]            ║
║                          ║
║ ## Analysis Complete     ║
║ pallets/flask            ║
║                          ║
║ Language:  Python        ║
║ Pattern:   LAYERED       ║
║ Confidence: HIGH         ║
║ Findings:  2 (1 CRIT.)   ║
║ Recommend: 6 (2 P1)      ║
║ Duration:  47s           ║
║                          ║
║ Report Contents          ║
║ 1. Executive Summary     ║
║ 2. Repository Overview   ║
║ 3. Architecture      ↕  ║
║ 4. Security Findings     ║
║ 5. Recommendations       ║
║ 6. Actionable Next Steps ║
║                          ║
║ # Executive Summary      ║
║ ···                      ║
╠══════════════════════════╣
║ [github.com/owner/·] [▶] ║
╚══════════════════════════╝
```

---

### Screen 5: History Sidebar (Expanded)

#### Desktop (1280px) — Sidebar focus

```
╔════════════════════════╗
║ ☰  ArchMind AI         ║
╠════════════════════════╣
║                        ║
║ [+ New Analysis     ] ║
║                        ║
║ [🔍 Search analyses  ]║
║                        ║
║ ── Pinned ──────────── ║
║ 📌 django/django       ║
║    Aug 1 · COMPLETE    ║
║                        ║
║ ── Today ───────────── ║
║ █ pallets/flask        ║
║   14:32 · COMPLETE     ║
║                        ║
║ ── Yesterday ────────  ║
║   fastapi/fastapi      ║
║   11:20 · COMPLETE     ║
║                        ║
║   owner/private-repo   ║
║   09:15 · FAILED       ║
║                        ║
║ ── This Week ────────  ║
║   torvalds/linux       ║
║   Aug 1 · COMPLETE     ║
║                        ║
║   psf/requests         ║
║   Jul 31 · COMPLETE    ║
║                        ║
║   ···  (more)      ↕  ║
║                        ║
╠════════════════════════╣
║ [⚙ Settings]           ║
║ [A] arafat · [↗] [⋮]  ║
╚════════════════════════╝
```

**Status indicators in sidebar items:**
- COMPLETE: no badge (clean, default)
- FAILED: small red dot
- RUNNING: animated pulse dot (if viewing a live session in another tab)
- Pinned: pin icon prefix

---

### Screen 6: Settings Panel

#### Desktop (1280px)

```
╔═══════════════╦══════════════════════════════════════════════════════════════╗
║ ☰ ArchMind AI ║  Settings                                          [✕ Close] ║
╠═══════════════╬══════════════════════════════════════════════════════════════╣
║               ║                                                              ║
║ General       ║  General                                                     ║
║ Account       ║  ─────────────────────────────────────────                  ║
║ About         ║                                                              ║
║               ║  Theme                                                       ║
║               ║  (●) System Default  ( ) Light  ( ) Dark                    ║
║               ║                                                              ║
║               ║  Language                                                    ║
║               ║  [  English (US)                        ▼  ]                ║
║               ║                                                              ║
║               ║  Enter Key Behavior                                          ║
║               ║  (●) Send message    ( ) New line                           ║
║               ║                                                              ║
║               ║  Default Model                                               ║
║               ║  [  ArchMind AI — Architecture Reviewer  ▼  ]               ║
║               ║                                                              ║
║               ║  ─────────────────────────────────────────                  ║
║               ║                                                              ║
║               ║  Account                                                     ║
║               ║  ─────────────────────────────────────────                  ║
║               ║                                                              ║
║               ║  Display Name                                                ║
║               ║  [  Arafat Rabbi                                ]            ║
║               ║                                                              ║
║               ║  Email                                                       ║
║               ║  [  kiroclaude902@gmail.com                    ]            ║
║               ║                                                              ║
║               ║  [  Change Password  ]                                       ║
║               ║                                                              ║
║               ║  [  Save Changes  ▶ ]                                       ║
║               ║                                                              ║
╚═══════════════╩══════════════════════════════════════════════════════════════╝
```

---

### Screen 7: Admin Panel

#### Desktop (1280px)

```
╔═══════════════╦══════════════════════════════════════════════════════════════╗
║ ☰ ArchMind AI ║  Admin Panel                                                 ║
╠═══════════════╬══════════════════════════════════════════════════════════════╣
║               ║                                                              ║
║ Dashboard     ║  Pipelines                                                   ║
║ Users         ║  ─────────────────────────────────────────                  ║
║ Pipelines  ◀  ║                                                              ║
║ Settings      ║  ╔══════════════════════════════════════════════════════╗   ║
║               ║  ║  ArchMind AI — Architecture Reviewer                ║   ║
║               ║  ║  ● Connected  │  v1.0.0  │  Port 9099              ║   ║
║               ║  ║                                                      ║   ║
║               ║  ║  Valves Configuration                                ║   ║
║               ║  ║  ─────────────────────                               ║   ║
║               ║  ║  ARCHMIND_API_URL                                    ║   ║
║               ║  ║  [ http://backend:8000                            ]  ║   ║
║               ║  ║                                                      ║   ║
║               ║  ║  ARCHMIND_API_KEY                                    ║   ║
║               ║  ║  [ ●●●●●●●●●●●●●●●●●●●●●●●●●  ] [👁 Show]        ║   ║
║               ║  ║                                                      ║   ║
║               ║  ║  POLL_INTERVAL_SECONDS                               ║   ║
║               ║  ║  [ 5                           ]                    ║   ║
║               ║  ║                                                      ║   ║
║               ║  ║  MAX_POLL_DURATION_SECONDS                           ║   ║
║               ║  ║  [ 1800                        ]                    ║   ║
║               ║  ║                                                      ║   ║
║               ║  ║  [ Save Valves ▶ ]  [ Test Connection ]             ║   ║
║               ║  ╚══════════════════════════════════════════════════════╝   ║
║               ║                                                              ║
║               ║  Pipeline Logs (last 50 lines)                              ║
║               ║  ─────────────────────────────                             ║
║               ║  2026-08-03 14:32:07 INFO job_submitted job_id=3fa85f64    ║
║               ║  2026-08-03 14:32:54 INFO job_complete report_id=a1b2c3d4  ║
║               ║  ···                                                    ↕   ║
╚═══════════════╩══════════════════════════════════════════════════════════════╝
```

---

### Screen 8: Error States

#### Invalid URL Error

```
╔══════════════════════════════════════════════════════╗
║                                                      ║
║  ⬡ ArchMind AI                              [⎘]    ║
║                                                      ║
║  ╔══════════════════════════════════════════════╗   ║
║  ║  ⚠  Input Error                            ║   ║
║  ╠══════════════════════════════════════════════╣   ║
║  ║                                              ║   ║
║  ║  Repository URL must begin with:            ║   ║
║  ║  https://github.com/                        ║   ║
║  ║                                              ║   ║
║  ║  Your input:                                ║   ║
║  ║  github.com/pallets/flask                   ║   ║
║  ║                                              ║   ║
║  ║  Correct format:                            ║   ║
║  ║  https://github.com/pallets/flask           ║   ║
║  ║                                              ║   ║
║  ╚══════════════════════════════════════════════╝   ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

#### Job Failed Error

```
╔══════════════════════════════════════════════════════╗
║                                                      ║
║  ⬡ ArchMind AI                              [⎘]    ║
║                                                      ║
║  ╔══════════════════════════════════════════════╗   ║
║  ║  ✕  Analysis Failed                        ║   ║
║  ╠══════════════════════════════════════════════╣   ║
║  ║                                              ║   ║
║  ║  Repository:  owner/private-repo            ║   ║
║  ║  Job ID:      3fa85f64-···-2c963f66afa6     ║   ║
║  ║                                              ║   ║
║  ║  Error:                                     ║   ║
║  ║  Repository clone failed — not found        ║   ║
║  ║  or repository is private.                  ║   ║
║  ║                                              ║   ║
║  ║  Possible causes:                           ║   ║
║  ║  · Repository is private                   ║   ║
║  ║  · URL is incorrect                        ║   ║
║  ║  · GitHub is temporarily unavailable       ║   ║
║   ║                                              ║   ║
║  ║  Submit a corrected URL below to retry.    ║   ║
║  ║                                              ║   ║
║  ╚══════════════════════════════════════════════╝   ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

#### Backend Unavailable

```
╔══════════════════════════════════════════════════════╗
║                                                      ║
║  ⬡ ArchMind AI                              [⎘]    ║
║                                                      ║
║  ╔══════════════════════════════════════════════╗   ║
║  ║  ✕  Service Unavailable                    ║   ║
║  ╠══════════════════════════════════════════════╣   ║
║  ║                                              ║   ║
║  ║  Cannot reach the ArchMind analysis         ║   ║
║  ║  backend. The service may be temporarily    ║   ║
║  ║  unavailable.                               ║   ║
║  ║                                              ║   ║
║  ║  Please try again in a few minutes.         ║   ║
║  ║  If this persists, contact your admin.      ║   ║
║  ║                                              ║   ║
║  ╚══════════════════════════════════════════════╝   ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

---

---

## 5. UX Decisions

### 5.1 Repository Submission

**Input field behavior:**
- Full-width text input in the chat input area
- Placeholder text: "Enter a GitHub repository URL — e.g. https://github.com/owner/repo"
- On paste: trim leading/trailing whitespace automatically
- No "validate on type" — only validate on submit (avoids distracting red states while user is typing)
- Accept both `https://github.com/owner/repo` and `https://github.com/owner/repo.git` — pipeline strips `.git` before submission
- Accept URLs embedded in natural language: "Can you review https://github.com/pallets/flask please?" — pipeline regex-extracts the URL
- On invalid URL: do not create a job; return inline error immediately without leaving the input empty (user can correct and resubmit)

**Submission trigger:**
- Enter key (configurable in Settings to be New Line instead)
- Click the ▶ send button

**Input disabled during analysis:**
- While a job is PENDING or RUNNING in the current conversation, the input field is disabled with placeholder text "Analysis in progress..."
- This prevents a user from accidentally submitting a second URL before the first is done
- The input re-enables on COMPLETE or FAILED status

---

### 5.2 Progress Display

**Philosophy:** Users must never feel uncertain about whether the system is working.

**Immediate acknowledgment (0s):**
The first streaming chunk arrives within 200ms of submission. This confirms the request was received.

**Progress checklist:**
The 8-item checklist (one per LangGraph node) gives users a mental model of the pipeline without exposing internal node names. The checklist uses human-readable labels:

```
- [ ] Job submitted
- [ ] Repository ingestion
- [ ] Code parsing
- [ ] Architecture analysis
- [ ] Security analysis
- [ ] Knowledge base retrieval
- [ ] Recommendation generation
- [ ] Report composition
```

**Why checklist (not spinner or progress bar):**
- Checklist communicates that there are distinct phases, not just "loading"
- Users can map their understanding of software analysis to the steps
- No false precision: we cannot know % complete without node events from the backend

**Elapsed time:**
Updated every 30 seconds during the poll loop: `*Elapsed: 30s — Analysis running...*`

This is the only live update between poll cycles. It confirms the connection is alive.

**What is NOT shown:**
- Per-node duration (backend doesn't emit node events)
- Estimated time remaining (no reliable basis for estimation)
- Progress percentage (would be fabricated)

---

### 5.3 Report Display

**Display order (always):**
1. Analysis complete header + timestamps
2. Metadata summary table
3. Section table of contents (text only, not interactive links)
4. Full report body (markdown_content verbatim)

**Why this order:**
- Metadata first = users get the headline result (pattern, confidence, finding count) before reading 3,000 words
- TOC second = navigation reference before the content it describes
- Full report third = comprehensive reading experience

**Streaming report body:**
Report is yielded in 512-character chunks. This allows the user to begin reading the Executive Summary while the Security Findings section is still rendering. Do not buffer the entire report and release it at once.

**Section headings:**
The report's Markdown uses `##` and `###` headings. OpenWebUI renders these with visual hierarchy. No additional heading treatment required.

**Code blocks:**
Security findings often include code snippets showing vulnerable patterns. OpenWebUI renders fenced code blocks with syntax highlighting. No additional code rendering required.

**Tables:**
Finding counts by severity are rendered as Markdown tables. OpenWebUI renders these with border styling. No additional table rendering required.

---

### 5.4 Large Report Handling

**What counts as "large":**
- Repos with many files: architecture analysis section may be 2,000+ words
- Repos with many findings: security section may contain 20+ individual findings
- Repos with deep dependency graphs: dependencies section may list 50+ packages

**Problem:**
OpenWebUI can stall visually if a very large block of Markdown is yielded as a single chunk.

**Solution:**
Pipeline yields `markdown_content` in chunks of no more than 512 characters. This caps the maximum time between renders at approximately 10ms per chunk at 50KB/s network throughput — imperceptible to the user.

**Reading long reports on desktop:**
The chat area is scrollable. The header (model selector) and input field remain sticky. Users scroll the report body while the UI chrome stays fixed.

**Reading long reports on mobile:**
At 375px, the metadata table collapses into a two-column layout (Field | Value). Section headings are styled at 120% font size. The TOC is displayed as a numbered list without additional styling.

**Very large repos (e.g., linux kernel, chromium):**
Backend enforces size limits (M16.3 — repository size pre-check). If a repo exceeds `MAX_REPO_SIZE_MB`, the backend returns a 422. Pipeline surfaces this as:

```
Repository Too Large

pallets/flask exceeds the maximum repository size limit.
ArchMind AI supports repositories up to [N] MB.
```

---

### 5.5 Multiple Analyses in One Session

**Scenario:** User submits two repos in the same conversation thread.

**Behavior:**
- Each submission = one user message + one pipeline response
- Both messages appear in the conversation thread sequentially
- Each response is self-contained (its own metadata card, TOC, report body)
- Visual separator (horizontal rule) between submissions

**Recommendation:**
For clarity, suggest users open a new conversation for each analysis. The pipeline system prompt includes: "For best results, use a new conversation per repository."

**If user submits in the same thread anyway:**
Works correctly. No technical issue. The two reports stack vertically and are both accessible by scrolling.

---

### 5.6 Conversation History Behavior

**Auto-naming:**
When a job completes, OpenWebUI can auto-name conversations. The pipeline returns a suggested title via the response metadata: `"pallets/flask — 2026-08-03"`.

**Manual rename:**
User can right-click any sidebar entry → Rename → type a custom name.

**Search:**
OpenWebUI's native search filters sidebar entries by conversation title. Since titles include the repo name, searching "flask" will find all flask analyses.

**Pinning:**
Users can pin important analyses. Pinned items appear at the top of the sidebar, above the date-grouped entries.

**Deletion:**
Users can delete conversations. This only deletes the OpenWebUI conversation record — it does NOT delete the report from Supabase. The Supabase report remains accessible via direct API call.

**Persistence:**
Conversations persist in OpenWebUI's database (SQLite file in named Docker volume). They survive container restarts as long as the named volume persists.

---

### 5.7 Returning to Previous Reports

**Method 1: Sidebar click**
Click any conversation in the left sidebar. The conversation loads from OpenWebUI's storage immediately, with no backend call.

**Method 2: Share link**
Each conversation has a shareable link (OpenWebUI native). Clicking the link opens the conversation directly.

**Method 3: Search**
Type the repo name in the sidebar search box. Matching conversations appear. Click to open.

**No "reload from backend" needed:**
The full report is stored in OpenWebUI's conversation history. Historical reports do not require the ArchMind backend to be running to be read. This is a significant reliability advantage.

---

---

## 6. Branding Guide

### 6.1 Product Identity

**Product name:** ArchMind AI  
**Tagline:** AI-powered Software Architecture Review  
**Voice:** Professional, precise, engineering-focused. No marketing fluff. Results over personality.  
**Tone in UI copy:** Direct. Informative. Confident without being presumptuous.

---

### 6.2 Logo

**Primary mark:**
Hexagon (⬡) symbol representing architectural structure, combined with the wordmark "ArchMind AI".

**Logo construction:**
```
  ⬡  ArchMind AI
```

**Hexagon rationale:**
- Hexagon = structural integrity (honeycomb architecture)
- Conveys pattern analysis and structure evaluation
- Geometric precision matches the tool's engineering focus
- Works at small sizes (sidebar favicon, browser tab)

**Logo placement:**
- Sidebar header (left, 24px height)
- Login page (centered, 40px height)
- Browser tab favicon (⬡ alone, 16x16)
- Admin panel header (24px height)

**What NOT to do:**
- Do not add gradients to the hexagon mark
- Do not use the hexagon alone without "ArchMind AI" in primary placement
- Do not resize the wordmark independently of the mark

---

### 6.3 Typography

**Primary typeface:** System UI stack (matches OpenWebUI's default, no custom font loading)

```
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, sans-serif;
```

**Monospace typeface (code blocks, job IDs, repo paths):**
```
font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
```

**Type scale:**
| Element | Size | Weight |
|---|---|---|
| Page title | 24px | 600 |
| Section heading (##) | 20px | 600 |
| Subsection heading (###) | 17px | 600 |
| Body text | 14px | 400 |
| Metadata table | 13px | 400 |
| Code blocks | 13px | 400 |
| Sidebar item primary | 14px | 500 |
| Sidebar item secondary | 12px | 400 |
| Button label | 14px | 500 |
| Status badge | 11px | 600 (all caps) |

**Why system fonts:**
OpenWebUI uses system fonts. Injecting a custom font increases page load time and requires font configuration that OpenWebUI doesn't natively support. System fonts match the host OS, feel native, and render well at all sizes.

---

### 6.4 Color Palette

All colors expressed as semantic roles, not hex values, to allow light/dark mode switching.

**Brand colors (used for key actions and identity):**
| Role | Light Mode | Dark Mode | Usage |
|---|---|---|---|
| Brand Primary | Indigo-600 (#4F46E5) | Indigo-400 (#818CF8) | Buttons, links, active states, submit CTA |
| Brand Secondary | Indigo-100 (#E0E7FF) | Indigo-900 (#312E81) | Button hover, selected sidebar item |

**Status colors:**
| Status | Light Mode | Dark Mode | Usage |
|---|---|---|---|
| Success (COMPLETE) | Green-600 (#16A34A) | Green-400 (#4ADE80) | Checkmarks, completion badges |
| Warning (RUNNING) | Amber-500 (#F59E0B) | Amber-400 (#FBBF24) | Progress pulse dot, elapsed time |
| Error (FAILED) | Red-600 (#DC2626) | Red-400 (#F87171) | Error states, failed badges, error cards |
| Info | Blue-600 (#2563EB) | Blue-400 (#60A5FA) | Job IDs, metadata secondary values |
| Neutral | Gray-600 (#4B5563) | Gray-400 (#9CA3AF) | Secondary text, timestamps |

**Architecture pattern badge colors:**
| Pattern | Color |
|---|---|
| LAYERED | Blue |
| MVC | Green |
| HEXAGONAL | Teal |
| SERVICE_BASED | Purple |
| MONOLITH_UNDIFFERENTIATED | Gray |
| UNKNOWN | Dark Gray |

**Severity colors (for security findings):**
| Severity | Color |
|---|---|
| CRITICAL | Red-600 |
| HIGH | Orange-500 |
| MEDIUM | Amber-500 |
| LOW | Blue-600 |

**Surface colors:**
| Role | Light Mode | Dark Mode |
|---|---|---|
| Background | White (#FFFFFF) | Gray-900 (#111827) |
| Sidebar background | Gray-50 (#F9FAFB) | Gray-950 (#030712) |
| Card background | White (#FFFFFF) | Gray-800 (#1F2937) |
| Border | Gray-200 (#E5E7EB) | Gray-700 (#374151) |
| Input background | White (#FFFFFF) | Gray-800 (#1F2937) |

---

### 6.5 Dark Mode

OpenWebUI ships dark mode. All color references above use semantic roles that map to OpenWebUI's built-in theme variables. No custom dark mode CSS is required.

**Dark mode trigger:** System preference (`prefers-color-scheme: dark`) or user setting in Settings → Theme.

---

### 6.6 Icons

**Icon set:** Heroicons v2 (ships with OpenWebUI). No additional icon library required.

**Key icon assignments:**
| Element | Icon |
|---|---|
| New Analysis | PlusCircle |
| Search | MagnifyingGlass |
| Settings | Cog6Tooth |
| Admin | ShieldCheck |
| Copy | ClipboardDocument |
| Share | ArrowTopRightOnSquare |
| Regenerate | ArrowPath |
| Delete | Trash |
| Pin | MapPin |
| Pipeline status OK | CheckCircle (green) |
| Pipeline status error | XCircle (red) |
| Warning | ExclamationTriangle |
| Show/hide API key | Eye / EyeSlash |

---

### 6.7 States

**Empty State:**
```
Centered in chat area.
⬡ [large hexagon, 48px, brand primary color]
"ArchMind AI"     [24px, 600 weight]
"Submit a GitHub repository URL to begin" [14px, gray-500]
```

**Loading State (pipeline processing):**
```
Spinner: three-dot animation (⠸ rotating) after elapsed time text
Color: brand primary
Size: 16px inline with text
```

**Progress State (polling):**
```
Checklist items: gray for pending, green checkmark for complete
Elapsed time: amber color, italic
```

**Error State:**
```
Card with red-50 background (light) / red-950 (dark)
Red-600 left border (4px)
ExclamationTriangle icon (red)
Bold error title
Regular body text with remediation suggestion
```

**Success State:**
```
Metadata table with green-50 header row tint (light) / green-950 (dark)
"Analysis Complete" heading with CheckCircle icon (green)
Clean card border (no color tinting on full report body — keeps reading experience neutral)
```

---

---

## 7. Component Inventory

### Implementation Categories

Every entry in this inventory belongs to one of three categories:

| Category | Description | Custom Code |
|---|---|---|
| **A — OpenWebUI Native** | Part of OpenWebUI's built-in React UI. We configure it via env vars; we do not write or modify its code. | None |
| **B — Pipeline Python Function** | A Python function in `pipelines/` that accepts inputs and returns a Markdown string. Not a React component. | Yes — Python |
| **C — OpenWebUI Auto-Generated (Valves)** | OpenWebUI reads the pipeline's `Valves(BaseModel)` Pydantic class and auto-generates a configuration form in the admin panel. | One Pydantic class |

**No custom React components are written in v1.0.** All interactive UI is OpenWebUI native. All pipeline output is plain Markdown text.

---

### Component: RepositoryInputField

**Category: A — OpenWebUI Native**

**Responsibility:** Accepts the user's GitHub URL as a chat message and submits it to the pipeline when the user presses Enter or clicks the send button.

**OpenWebUI native behaviour:**
- Full-width text input in the chat footer area
- Placeholder text configurable via env var (verify `OPENWEBUI_...` at F1; fallback: OpenWebUI default)
- Input is automatically disabled by OpenWebUI while the pipeline is streaming a response — the "disabled during analysis" behaviour requires no custom implementation
- Input re-enables automatically when the pipeline response stream ends (COMPLETE or FAILED)

**Server-side validation (pipeline, not browser):**
- URL validation occurs in `url_extractor.py` after the message reaches the pipeline
- No browser-side JavaScript URL validation exists in v1.0
- Invalid input produces an ErrorCard Markdown response from the pipeline
- Whitespace trimming, `.git` suffix stripping, and natural-language URL extraction all happen in `url_extractor.py`

**v1.0 constraint:** No client-side validation. No custom React code.

---

### Component: ProgressChecklist

**Category: B — Pipeline Python Function**

**Responsibility:** Generates a Markdown checklist block showing pipeline progress and elapsed time. Implemented in `status_formatter.py`.

**Python function inputs:**

| Input | Type | Description |
|---|---|---|
| `job_submitted` | `bool` | True after `POST /api/v1/jobs` returns 202 |
| `is_running` | `bool` | True while job status is PENDING or RUNNING |
| `is_complete` | `bool` | True when job reaches COMPLETE or FAILED |
| `elapsed_seconds` | `int` | Wall-clock seconds since pipeline received user message |

**Markdown output format:**

```markdown
### Pipeline Status

- [x] Job submitted ✓
- [ ] Repository ingestion
- [ ] Code parsing
- [ ] Architecture analysis
- [ ] Security analysis
- [ ] Knowledge base retrieval
- [ ] Recommendation generation
- [ ] Report composition

*Elapsed: 30s — Analysis running...*
```

**v1.0 accuracy constraint:** At v1.0, the backend emits no node-level progress events. Only `Job submitted` can be checked `[x]` during the RUNNING phase. All other 7 items remain unchecked until job COMPLETE, at which point the entire checklist collapses into the AnalysisHeader completion summary. The function must not imply granular per-node progress it cannot deliver.

**Elapsed time:** Rendered as `*italic*` Markdown only. No color enforcement — amber color is not achievable in plain Markdown without CSS injection.

---

### Component: MetadataCard

**Category: B — Pipeline Python Function**

**Responsibility:** Generates a Markdown table summarising analysis results immediately after job completion. Implemented in `report_formatter.py`. The card only exists after a completed report is fetched — there is no intermediate loading or shimmer state.

**Python function input:** Full `ReportResponse.metadata` dict (typed as `ReportMetadataResponse`).

**Markdown output format:**

```markdown
| Field                  | Value              |
|------------------------|--------------------|
| Primary Language       | Python             |
| Architecture Pattern   | 🔵 LAYERED         |
| Confidence             | ✅ HIGH             |
| Security Findings      | 3 (1 🔴 CRITICAL)  |
| Recommendations        | 6 (2 P1)           |
| Files Analyzed         | 89                 |
| Analysis Duration      | 47 seconds         |
| RAG Chunks Used        | 7                  |
| Total LLM Tokens       | 14,203             |
```

**Sub-element patterns (Markdown text, not React components):**

| Sub-element | Markdown representation |
|---|---|
| Architecture pattern | Emoji prefix + text: `🔵 LAYERED`, `🟢 MVC`, `🩵 HEXAGONAL`, `🟣 SERVICE_BASED`, `⚪ MONOLITH_UNDIFFERENTIATED`, `⚫ UNKNOWN` |
| Confidence level | Emoji prefix + text: `✅ HIGH`, `⚠️ MEDIUM`, `🔴 LOW` |
| Finding count | Formatted string: `"3 (1 🔴 CRITICAL, 2 🟡 MEDIUM)"` |
| Null finding count | `"0 (none)"` — handles `highest_severity_finding: null` from API |
| Stat row | Standard Markdown table row: `"| Field | Value |"` |

**No loading state, no shimmer, no animation.** The MetadataCard is yielded once, after `GET /api/v1/reports/{report_id}` returns. It does not appear before then.

---

### Component: ReportTableOfContents

**Category: B — Pipeline Python Function**

**Responsibility:** Generates a Markdown numbered list of section titles from the report's `sections[]` array. Implemented in `report_formatter.py` as a helper function.

**Python function input:** `sections: list[dict]` — the `sections[]` array from `ReportResponse`, in backend-provided order.

**Markdown output format:**

```markdown
### Report Contents

1. Executive Summary
2. Repository Overview
3. Architecture Assessment
4. Security Findings
5. Recommendations
6. Actionable Next Steps
```

**Implementation rules:**
- Use `section.section_title` only — never expose `section.section_key` to the user
- Do not re-sort — trust the backend's `section_order` field; iterate `sections[]` as received
- Text-only at v1.0: no anchor links, no scroll tracking, no interactive navigation

---

### Component: MarkdownReportBody

**Category: A — OpenWebUI Native Renderer**

**Responsibility:** OpenWebUI's built-in Markdown renderer handles all report body display. The pipeline streams `markdown_content` verbatim in 512-character chunks. OpenWebUI appends each chunk to the chat message and re-renders the growing Markdown string. No custom renderer is written.

**Pipeline output:** `markdown_content` from `ReportResponse`, streamed in chunks of ≤512 characters. No post-processing applied to the report body — streamed verbatim.

**Confirmed Markdown feature compatibility (reference for pipeline output authors):**

| Feature | Markdown syntax | Used for |
|---|---|---|
| Section headings | `##`, `###`, `####` | Report section hierarchy |
| Code blocks | ` ```lang ``` ` (fenced) | Security finding examples, vulnerable code |
| Tables | `\| col \| col \|` | Finding counts, dependency lists |
| Bold / italic / inline code | `**`, `*`, `` ` `` | Emphasis, identifiers |
| Ordered / unordered lists | `1.`, `-` | Recommendations, finding lists |
| Horizontal rules | `---` | Section dividers |
| Blockquotes | `>` | RAG source citations |

**No custom implementation required.** OpenWebUI renders all of the above.

---

### Component: Status Patterns (replaces StatusBadge)

**Category: B — Pipeline Markdown Text Patterns**

**Responsibility:** Represent job status within pipeline Markdown output using Unicode characters and emoji. No colored pill badges, no CSS, no pulse animations are achievable in plain Markdown at v1.0.

**Markdown status representations:**

| Status | Markdown text | Context |
|---|---|---|
| Submitting | `*Connecting to ArchMind backend...*` | First yield before POST /jobs |
| Pending / Running | `⠸ Analysis running...` (static character) | Keepalive line during poll loop |
| Complete | `✅ Analysis complete (47s)` | Checklist summary on COMPLETE |
| Failed | `❌ Analysis failed` | On FAILED terminal status |

**Sidebar conversation title status:** FAILED analyses include `— FAILED` suffix in the conversation title string (e.g., `"owner/repo — FAILED — 2026-08-03"`). This is the only mechanism for surfacing status in the sidebar — plain text in the title, not a visual badge. COMPLETE conversations have no suffix (clean default).

**No animated pulse, no colored pills, no CSS.** All status representations are static Unicode characters or emoji in Markdown text.

---

### Component: ConversationHistoryItem

**Category: A — OpenWebUI Native**

**Responsibility:** Single entry in the left sidebar conversation history. OpenWebUI owns this component entirely — all visual styling, hover actions, date grouping, pin state, and active highlighting are OpenWebUI's native behaviour.

**Pipeline influence (only one):** The conversation title string. Format: `"repo-name — YYYY-MM-DD"` (e.g., `"pallets/flask — 2026-08-03"`). For failed analyses: `"repo-name — FAILED — YYYY-MM-DD"`. The mechanism for setting this title (pipeline metadata, response body, or OpenWebUI auto-naming from first message) must be verified at F1 (Checklist item C3).

**OpenWebUI provides natively (no implementation required):**
- Date grouping (Today / Yesterday / This Week)
- Hover actions: Pin to top, Share link, Delete (with confirmation)
- Active/selected highlighting
- Search filtering by title

---

### Component: PipelineStatusIndicator

**Category: A — OpenWebUI Native**

**Responsibility:** Displays pipeline server connectivity status in the admin panel. OpenWebUI automatically polls the Pipelines server and renders the connected / disconnected / error state. No custom implementation required.

**Pipeline influence (only one):** The `version` attribute declared in the pipeline Python class:

```python
# In archmind_pipeline.py
class Pipeline:
    version = "1.0.0"
```

OpenWebUI reads this attribute and displays it alongside the connection status in the admin panel Pipelines page.

---

### Component: ValvesForm

**Category: C — OpenWebUI Auto-Generated (Valves)**

**Responsibility:** Admin UI for editing pipeline runtime configuration. OpenWebUI reads the pipeline's `Valves(BaseModel)` Pydantic class definition and auto-generates a settings form — one input field per Pydantic field, using the field's type annotation to determine the input type.

**Pipeline implementation:** Define the `Valves` class inside the pipeline:

```
Valves fields:
  ARCHMIND_API_URL          str   default: "http://backend:8000"
  ARCHMIND_API_KEY          str   default: ""
  POLL_INTERVAL_SECONDS     int   default: 5
  MAX_POLL_DURATION_SECONDS int   default: 1800
```

**API key masking:** OpenWebUI does not automatically mask string fields. Whether `ARCHMIND_API_KEY` renders as a password input depends on the deployed OpenWebUI version. **Must be verified at F1.** If masking is not automatic, the admin must be instructed not to expose this screen to non-admin users. Add to F1 Checklist item C3.

**Save behaviour:** OpenWebUI handles the Save action internally. Updated Valve values are available to the pipeline on the next `pipe()` invocation. The pipeline does not implement a save handler.

---

### Component: DependencyHealthBadge

**Category: B — Pipeline Python Function (health warning only)**

**Responsibility:** Generates a Markdown warning block prepended to the pipeline system prompt when any backend dependency is degraded. Implemented as `format_health_warning()` in `archmind_pipeline.py`.

**Python function input:** `health: dict` — the full `HealthResponse` dict from `GET /api/v1/health`.

**Trigger condition:** Any dependency with status other than `"ok"`. Status values sourced directly from `HealthResponse.dependencies` in `backend/api/schemas/health_schemas.py`:

```
"ok" | "failed" | "unreachable" | "collection_missing" | "unknown"
```

**Markdown output (when degraded):**

```markdown
> ⚠️ **System Warning**
>
> One or more backend dependencies are degraded:
> - Qdrant: `collection_missing` — knowledge base not loaded. Recommendations may be lower quality.
> - Gemini: `failed` — LLM unavailable. Analysis will fail.
>
> Contact your administrator if this persists.
```

**When all dependencies are `"ok"`:** function returns `None` — no warning block emitted.

**Scope at v1.0:** Pipeline system prompt only. No custom admin dashboard health widget. Admin dashboard dependency health is out of v1.0 scope.

---

### Component: ErrorCard

**Category: B — Pipeline Python Function**

**Responsibility:** Generates a Markdown error block for each failure mode. Implemented as error handler functions in `archmind_pipeline.py`. Uses Markdown blockquote (`>`) for visual left-border treatment — no CSS styling.

**Error type taxonomy:**

| Type | Trigger | `jobId` present |
|---|---|---|
| `invalid_url` | URL validation fails before `POST /jobs` | No — job never created |
| `job_failed` | Backend `status: "FAILED"` | Yes |
| `service_unavailable` | Connection refused or 5xx from backend | No |
| `rate_limited` | 429 response — distinguish `detail` field: `"Server at capacity"` vs rate limit | No |
| `timeout` | Poll loop exceeds `MAX_POLL_DURATION_SECONDS` | Yes |
| `repo_too_large` | 422 response from backend (available after **M16.3** deployment) | No |

**Markdown output template (example — `job_failed`):**

```markdown
> ❌ **Analysis Failed**
>
> **Repository:** owner/repo
> **Job ID:** `3fa85f64-5717-4562-b3fc-2c963f66afa6`
>
> **Error:** Repository clone failed — not found or repository is private.
>
> Possible causes:
> - Repository is private (ArchMind analyzes public repositories only)
> - URL is incorrect
> - GitHub is temporarily unavailable
>
> Submit a corrected URL to try again.
```

**No CSS properties, no border colours, no background tints.** The blockquote `>` prefix is the only available visual treatment in plain Markdown.

---

### Component: WelcomeMessage

**Category: B — Static String in Pipeline Class**

**Responsibility:** The system prompt displayed in every new conversation. Explains the tool's purpose, accepted input format, and an example. Set once at pipeline class definition — not regenerated per conversation.

**Implementation:** A static multi-line string returned by the pipeline's system prompt method (or equivalent). Content is static and only changes when the pipeline Python file is updated and reloaded.

**Content (final copy — do not alter without updating this document):**

```
ArchMind AI — Software Architecture Reviewer

Submit a GitHub repository URL to receive a comprehensive engineering audit report.

Supported formats:
  https://github.com/owner/repository
  https://github.com/owner/repository.git

Example:
  https://github.com/pallets/flask

For best results, use a new conversation per repository.
```

---

### Component: AnalysisHeader

**Category: B — Pipeline Python Function**

**Responsibility:** Generates the Markdown header block that opens every pipeline response. Implemented as the first yield sequence in `archmind_pipeline.py`. The Job ID is not displayed until after the backend confirms job creation.

**Yield sequence (two-phase):**

```
Phase 1 — immediate (before POST /jobs):
  Yield: "## ArchMind AI — Submitting...\n\n**Repository:** repo-name\n"

Phase 2 — after POST /jobs returns 202:
  Yield: "**Job ID:** `{confirmed_job_id}`\n**Submitted:** {utc_timestamp}\n\n---\n"
```

**Why two phases:** Displaying a Job ID before the backend creates one is deceptive — if the `POST /jobs` call fails (429, 5xx, connection error), the user would have seen a Job ID for a job that never existed. The pipeline yields an initial acknowledgment immediately (sub-200ms), then yields the confirmed Job ID only after 202 is received.

**Python function inputs (Phase 2):**

| Input | Type | Source |
|---|---|---|
| `repo_name` | `str` | Extracted from URL by `url_extractor.py` |
| `job_id` | `str` | From `POST /jobs` 202 response body |
| `submitted_at` | `str` | Pipeline's own UTC timestamp at moment of `POST /jobs` call |

---

### OpenWebUI Admin — User Management

*Not a component — operational capability only.*

OpenWebUI's admin panel includes a native user management table (display name, email, role, created date, last active) with per-row actions: Edit, Reset password, Suspend, Delete. This is built into OpenWebUI and requires no custom implementation. Refer to `frontend/docs/DEPLOYMENT_GUIDE.md` for admin onboarding instructions.

---

### Component Implementation Mapping

| Component | Category | Implementation File | Phase |
|---|---|---|---|
| RepositoryInputField | A — OpenWebUI Native | — (env var config only) | F1 |
| ProgressChecklist | B — Pipeline Python Function | `pipelines/status_formatter.py` | F2 |
| MetadataCard | B — Pipeline Python Function | `pipelines/report_formatter.py` | F2 |
| ReportTableOfContents | B — Pipeline Python Function | `pipelines/report_formatter.py` | F2 |
| MarkdownReportBody | A — OpenWebUI Native | — (no implementation) | — |
| Status Patterns | B — Pipeline Markdown Text | `pipelines/archmind_pipeline.py` | F2 |
| ConversationHistoryItem | A — OpenWebUI Native | — (title string only) | F2 |
| PipelineStatusIndicator | A — OpenWebUI Native | `version` attr in `archmind_pipeline.py` | F2 |
| ValvesForm | C — OpenWebUI Auto-Generated | `Valves(BaseModel)` in `archmind_pipeline.py` | F2 |
| DependencyHealthBadge | B — Pipeline Python Function | `pipelines/archmind_pipeline.py` | F4 |
| ErrorCard | B — Pipeline Python Function | `pipelines/archmind_pipeline.py` | F2 |
| WelcomeMessage | B — Static Pipeline String | `pipelines/archmind_pipeline.py` | F3 |
| AnalysisHeader | B — Pipeline Python Function | `pipelines/archmind_pipeline.py` | F2 |

---

---

## 8. Frontend Folder Architecture

```
frontend/
│
├── docs/
│   ├── PHASE_0_ARCHITECTURE.md          ← This document
│   ├── PIPELINE_API_CONTRACT.md         ← OpenWebUI Pipeline interface spec (F1 — placeholder; complete before F2)
│   ├── ARCHMIND_API_CONTRACT.md         ← Backend API surface consumed by pipeline (F1 — placeholder; complete before F2)
│   └── DEPLOYMENT_GUIDE.md             ← How to deploy OpenWebUI + Pipelines (F5)
│
├── pipelines/
│   ├── __init__.py                      ← Python package marker; enables imports from frontend/tests/
│   ├── archmind_pipeline.py             ← Main pipeline class (F2)
│   ├── archmind_client.py               ← HTTP client for ArchMind backend (F2)
│   ├── url_extractor.py                 ← GitHub URL parsing and validation (F2)
│   ├── status_formatter.py              ← Progress checklist Markdown builder (F2)
│   ├── report_formatter.py              ← Metadata card + TOC + body assembler (F2)
│   └── requirements.txt                 ← Pipeline Python dependencies (httpx, pydantic, pytest, respx)
│
├── tests/                               ← Separated from pipelines/ — prevents Pipelines server loading test files as pipelines
│   ├── __init__.py
│   ├── conftest.py                      ← Shared pytest fixtures: mock HTTP responses, sample JobStatusResponse, ReportResponse, HealthResponse
│   ├── test_url_extractor.py            ← URL validation unit tests (F2)
│   ├── test_status_formatter.py         ← Progress display unit tests (F2)
│   ├── test_report_formatter.py         ← Report assembly unit tests (F2)
│   ├── test_archmind_client.py          ← HTTP client unit tests (F4)
│   └── test_pipeline_integration.py     ← Full pipeline mock tests (F4)
│
├── configs/
│   ├── openwebui.env.example            ← All OpenWebUI env vars documented
│   ├── pipelines.env.example            ← Pipeline env vars documented
│   └── nginx.conf.example               ← Reverse proxy config (F5)
│
├── branding/
│   ├── BRAND_GUIDE.md                   ← Color palette, typography, icon refs
│   ├── logo.svg                         ← Hexagon + wordmark SVG
│   └── favicon.svg                      ← Hexagon only, for browser tab
│
├── deployment/
│   ├── docker-compose.yml               ← Frontend-only compose: OpenWebUI + Pipelines server (F5). Backend runs separately.
│   ├── docker-compose.dev.yml           ← Dev overrides (hot reload, debug)
│   └── healthcheck.sh                   ← Smoke test script (F5)
│
├── examples/                            ← OPTIONAL — manual testing and demos only; not loaded by Pipelines server
│   ├── sample_report.md                 ← Example pipeline output: complete analysis
│   ├── sample_progress.md               ← Example pipeline output: in-progress checklist
│   └── sample_error.md                  ← Example pipeline output: error card variants
│
└── README.md                            ← Frontend quick-start guide
```

**Rationale for this structure:**

- `docs/` — design documentation lives adjacent to implementation, not in a separate wiki. Future engineers find architecture decisions here. `PIPELINE_API_CONTRACT.md` and `ARCHMIND_API_CONTRACT.md` are created at F1 as placeholders and completed before F2 implementation begins.
- `pipelines/` — all pipeline application code in one directory. The Pipelines server mounts this directory and hot-reloads on file change. `__init__.py` makes `pipelines/` a Python package so test files can import from it without `sys.path` manipulation. `requirements.txt` documents all Python dependencies needed by the pipeline (e.g. `httpx`, `pydantic`) and by the test suite (e.g. `pytest`, `respx`); the Pipelines server installs from this file at container startup.
- `tests/` — kept outside `pipelines/` deliberately. The Pipelines server scans its mounted directory for pipeline classes; test files named `test_*.py` contain pytest fixtures, not `class Pipeline:` definitions. Nesting tests inside the mount point risks the server attempting to load them as pipelines, causing startup errors. Separate `tests/` directory eliminates that risk entirely.
- `configs/` — example configuration files prevent secrets being accidentally committed while ensuring all required environment variables are documented.
- `branding/` — brand assets in version control. Logo and favicon are SVG (scalable, small, versionable).
- `deployment/` — deployment artifacts separated from application code. `docker-compose.yml` is **frontend-only**: it orchestrates OpenWebUI and the Pipelines server. It does **not** include the ArchMind backend, Qdrant, or Supabase — those run under their own deployment configuration. The backend must be reachable at the URL configured in the `ARCHMIND_API_URL` Valve.
- `examples/` — **optional directory**; not mounted by the Pipelines server and not part of any milestone deliverable. Contains static Markdown files showing what the pipeline output looks like for a complete report, an in-progress job, and each error type. Used for manual testing, demos, and onboarding new contributors without requiring a live backend.

**What is NOT in this folder:**

- No `node_modules/` — OpenWebUI is deployed as a pre-built Docker image, not built from source
- No `src/` — there is no custom React/Vue application; OpenWebUI is the shell
- No `public/` — static assets are served by OpenWebUI's built-in static server or a reverse proxy
- No `tsconfig.json`, `package.json` — no JavaScript build step for v1.0

---

---

## 9. Frontend Roadmap Review

### Review of F1–F5 Against Phase 0 Findings

After completing Phase 0, several refinements improve the roadmap.

---

#### F0: Phase 0 Sign-Off (Gate — no implementation)

**Type:** Gate milestone. Zero implementation deliverables. F1 cannot begin until all F0 criteria are met.

**F0 criteria:**
- All Section J checklist items (J1–J6) signed off
- `frontend/docs/PIPELINE_API_CONTRACT.md` completed — not a placeholder
- `frontend/docs/ARCHMIND_API_CONTRACT.md` completed — not a placeholder
- Branding assets created by design: `frontend/branding/logo.svg` and `frontend/branding/favicon.svg` exist
- Section A checklist (A1–A6) resolved: Docker, ports, backend running, API key generated and tested
- Section C checklist (C1–C5) resolved: OpenWebUI and Pipelines Docker image versions locked
- Section E checklist (E1–E5) resolved: branding assets and color palette confirmed
- Section I decisions (I1–I6) answered by project owner

---

#### F1: OpenWebUI Deployment & Core Wiring

**Status:** Correct. No implementation changes.

**Addition:** F1 must also configure OpenWebUI branding (WEBUI_NAME, DEFAULT_MODELS, ENABLE_SIGNUP) as part of the initial deployment. This was mentioned in F3 but belongs in F1 — it is a deployment concern, not a polish concern. Move branding env var configuration from F3 into F1.

**Updated F1 completion criteria:**
- All prior F1 criteria
- OpenWebUI header shows "ArchMind AI" branding
- ENABLE_SIGNUP=false is configured
- DEFAULT_MODELS is set to the ArchMind pipeline

---

#### F2: Core Pipeline — Submit, Poll, Retrieve

**Status:** Revised.

**Clarification:** The report formatter must generate the metadata card using the exact field mapping defined in `ReportMetadataResponse` (from `backend/api/schemas/report_schemas.py`). Must not add fields absent from the schema. Must gracefully handle `null` for `highest_severity_finding` — this field is `None` when a repository has no security findings.

**Added to F2 — WelcomeMessage:** System prompt implemented in F2. Without it the input field gives no guidance during F2 testing. Implementation is a single static string — zero risk. Content defined in Section 7 (Component Inventory).

**Added to F2 — ErrorCard (all 6 types):** Core error cases (`invalid_url`, `job_failed`, `service_unavailable`) are required for F2 exit criteria. Cannot verify error handling without the cards. All 6 types implemented in F2; copy polish deferred to F3.

**Added to F2 — ReportTableOfContents:** Part of the core report display path. Implemented in F2 alongside MetadataCard in `report_formatter.py`.

**F2 obligation — job guard research and prototype:**
The per-conversation job guard requires knowing whether the `Pipeline` class is a singleton (one instance for all conversations) or re-instantiated per `pipe()` call. This is not an F1 blocker — it is an F2 engineering investigation.

F2 must:
1. Research how the locked OpenWebUI Pipelines version manages `Pipeline` class instantiation.
2. Prototype a job guard using the identified mechanism.
3. Document the validated state management approach in `frontend/docs/PIPELINE_API_CONTRACT.md`.

This is a research and prototype obligation in F2. The production guard is implemented in F4 using the documented approach.

**Report streaming:** 512-character chunk size (Section D5) is kept as specified. Validate Markdown rendering behavior during F2/F3 before changing the chunking algorithm.

---

#### Engineering Review Checkpoint (between F2 and F3)

**Type:** Review gate. Zero implementation deliverables. F3 cannot begin until this checkpoint passes.

**Purpose:** Confirm the F2 pipeline is correct on the core path before F3 polish begins. Catch design or correctness issues before building UX on top of them.

**Checkpoint must confirm:**
- Full analysis round-trip end-to-end: URL → job submitted → poll loop → COMPLETE → report displayed
- All 6 ErrorCard types render correctly against `frontend/examples/sample_error.md`
- WelcomeMessage displays in new conversations
- ReportTableOfContents renders from `sections[]` titles
- MetadataCard handles `null` `highest_severity_finding` without crash
- Pipeline object lifecycle documented in `PIPELINE_API_CONTRACT.md`
- Job guard prototype behaviour documented
- Unit tests passing: `test_url_extractor.py`, `test_status_formatter.py`, `test_report_formatter.py`

---

#### F3: UX Polish & Error Experience

**Status:** Revised. Scope reduced to UX polish only.

**Moved to F2:** WelcomeMessage, ErrorCard implementation (all 6 types), ReportTableOfContents.

**Moved to F1:** Branding configuration (WEBUI_NAME, etc.)

**F3 scope — UX polish only:**
- Streaming progress time-elapsed updates: elapsed seconds appended to keepalive lines (e.g., `⠸ Analysis running... (32s)`)
- Streaming verification: confirm 512-char chunks render without visible Markdown artifacts in the chosen OpenWebUI version; adjust chunk size only if validation shows problems
- Error card copy polish: review all 6 error card message texts for clarity; update copy only, not structure
- Conversation title format confirmed working (Checklist item C3): `"repo-name — YYYY-MM-DD"` for COMPLETE, `"repo-name — FAILED — YYYY-MM-DD"` for FAILED

---

#### F4: Pipeline Hardening & Resilience

**Status:** Revised.

**Renamed:** F4.3 "Concurrent request guard" → "per-conversation job guard." The guard ensures a single conversation cannot have two active jobs simultaneously. It does not globally limit concurrent requests — that is the backend's responsibility via `MAX_CONCURRENT_JOBS`.

**F4 — production job guard implementation:** Using the state management approach researched and documented in F2, implement the production per-conversation job guard in `archmind_pipeline.py`. The implementation approach is not prescribed here — it depends on the F2 research outcome and must be read from `PIPELINE_API_CONTRACT.md`.

**Added to F4 exit criteria — live integration test:** Before F5 production deployment, a full integration test must pass: submit a real public GitHub URL from the F4 environment and confirm a complete report is returned. Qdrant must be loaded and all backend dependencies must be `"ok"`. This is the first verified test of the full chain: OpenWebUI → Pipeline → Backend → Qdrant → Gemini → Report.

---

#### F5: Production Deployment Integration

**Status:** Correct. No changes needed.

**Clarification:** F5 must include updating `settings.cors_origins` in the backend configuration to include the production OpenWebUI domain. This is a backend config change (`.env` update), not a code change.

**Scope clarification:** `frontend/deployment/docker-compose.yml` is frontend-only — it orchestrates OpenWebUI and the Pipelines server. The ArchMind backend, Qdrant, and Supabase run under their own deployment configuration. The backend must be reachable at the URL configured in the `ARCHMIND_API_URL` Valve.

---

### Revised Phase Summary

| Phase | Type | Title | Key Change |
|---|---|---|---|
| F0 | Gate | Phase 0 Sign-Off | **New** — contract docs complete, branding assets ready, I1–I6 decided |
| F1 | Implementation | OpenWebUI Deployment & Core Wiring | + Branding env vars moved in from F3 |
| F2 | Implementation | Core Pipeline: Submit, Poll, Retrieve | + WelcomeMessage, ErrorCard, TOC moved in from F3; + job guard research/prototype |
| ↓ | **Review Gate** | **Engineering Review Checkpoint** | **New** — confirms F2 correctness before F3 begins |
| F3 | Implementation | UX Polish & Error Experience | Scope reduced — time-elapsed, streaming verification, copy polish, conversation title |
| F4 | Implementation | Pipeline Hardening & Resilience | + Production job guard (from F2-validated approach); + live integration test exit criterion |
| F5 | Implementation | Production Deployment Integration | + CORS update documented; + frontend-only compose scope clarified |

---

---

## 10. Implementation Readiness Checklist

This checklist must be completely resolved before any F1 implementation begins. All items are currently OPEN unless marked RESOLVED.

---

### Section A: Environment & Infrastructure

- [ ] **A1.** Docker Desktop (or equivalent) is installed and running on the development machine
- [ ] **A2.** `docker compose version` returns ≥ 2.0 (V2 syntax required)
- [ ] **A3.** Ports 3000 (OpenWebUI), 9099 (Pipelines) are free on the development machine
- [ ] **A4.** The ArchMind backend can be started locally with `uvicorn api.main:create_app --factory` without errors
- [ ] **A5.** A valid `ARCHMIND_API_KEY` (≥32 chars) has been generated and is available for pipeline configuration
- [ ] **A6.** The backend `X-API-Key` header is confirmed working: `curl -H "X-API-Key: {key}" http://localhost:8000/api/v1/health` returns 200

---

### Section B: Backend API Contract Verification

- [ ] **B1.** `POST /api/v1/jobs` with a valid GitHub URL returns 202 with `job_id`, `status: "PENDING"`, `message`
- [ ] **B2.** `GET /api/v1/jobs/{job_id}` returns the correct lifecycle states: PENDING → RUNNING → COMPLETE/FAILED
- [ ] **B3.** `GET /api/v1/jobs/{job_id}` on a COMPLETE job includes a non-null `report_id`
- [ ] **B4.** `GET /api/v1/reports/{report_id}` returns all required fields: `markdown_content`, `sections[]`, `metadata`
- [ ] **B5.** `metadata.highest_severity_finding` is confirmed to be `null` (not absent) when no findings exist
- [ ] **B6.** `POST /api/v1/jobs` without an API key returns 401
- [ ] **B7.** `POST /api/v1/jobs` with an invalid GitHub URL (not starting with `https://github.com/`) returns 422 Unprocessable Entity (FastAPI returns 422, not 400, for Pydantic `field_validator` failures)
- [ ] **B8.** `GET /api/v1/health` returns 200 without an API key (unauthenticated, as designed)
- [ ] **B9.** Health response `dependencies` field includes `gemini`, `qdrant`, `supabase` with their probe statuses

---

### Section C: OpenWebUI Version Lock

- [ ] **C1.** Target OpenWebUI Docker image tag is locked (do not use `latest` — use a specific version tag)
- [ ] **C2.** Target Pipelines Docker image tag is locked (match to OpenWebUI version)
- [ ] **C3.** Confirm the Pipelines API interface: `pipe(user_message, model_id, messages, body)` method signature is current for the chosen version
- [ ] **C4.** Confirm `Valves` (BaseModel subclass) is supported in the chosen Pipelines version
- [ ] **C5.** Confirm AsyncGenerator (`async def pipe(...) -> AsyncGenerator`) is supported (not just sync generators)

---

### Section D: Pipeline Design Decisions

- [ ] **D1.** URL extraction regex is finalized: handles embedded URLs, strips .git suffix, rejects non-GitHub domains
- [ ] **D2.** Poll interval default (5 seconds) is agreed — not too aggressive on the backend, not too slow for UX
- [ ] **D3.** Max poll duration (1800 seconds) is agreed — covers the largest realistic repo analysis
- [ ] **D4.** Keepalive interval (every 30 seconds yield a dot) is agreed — prevents OpenWebUI from closing the stream
- [ ] **D5.** Chunk size for report streaming (512 chars) is agreed
- [ ] **D6.** Per-conversation job guard behavior is agreed: second submission while job is active returns an error message, does not submit a new job
- [ ] **D7.** Error message format for each error type is finalized (see Section 7 — Component: ErrorCard)

---

### Section E: Branding Assets

- [ ] **E1.** ArchMind AI hexagon + wordmark SVG is created and available at `frontend/branding/logo.svg`
- [ ] **E2.** Favicon SVG (hexagon only, 16x16 optimized) is created at `frontend/branding/favicon.svg`
- [ ] **E3.** Color palette is confirmed (see Section 6.4 of this document)
- [ ] **E4.** WEBUI_NAME value is agreed: `"ArchMind AI"`
- [ ] **E5.** Custom favicon upload to OpenWebUI is confirmed supported by the chosen OpenWebUI version

---

### Section F: Network & Security

- [ ] **F1.** Internal Docker network names are agreed (backend, frontend, data nets)
- [ ] **F2.** Backend `cors_origins` setting is confirmed to include `http://localhost:3000` for local dev
- [ ] **F3.** Pipeline server is confirmed to be on the same internal network as the backend — not exposed to public internet
- [ ] **F4.** OpenWebUI's HTTPS configuration strategy for production is decided (reverse proxy: nginx/Traefik vs managed TLS from cloud provider)
- [ ] **F5.** OpenWebUI's own secret key (`WEBUI_SECRET_KEY`) generation method is decided: `openssl rand -hex 32`

---

### Section G: Data Persistence

- [ ] **G1.** Named Docker volume strategy for OpenWebUI's conversation history is decided: `openwebui_data`
- [ ] **G2.** Database choice from I1 is implemented in `frontend/deployment/docker-compose.yml`: either default SQLite volume mount or `DATABASE_URL` env var pointing to Supabase PostgreSQL. *(Decision owned by I1 — resolve I1 first, then verify here.)*
- [ ] **G3.** Backup strategy for OpenWebUI conversation history is decided

---

### Section H: Testing Strategy Locked

- [ ] **H1.** Pipeline unit test framework agreed: `pytest` with `pytest-asyncio` for async pipeline tests
- [ ] **H2.** HTTP mock library for pipeline tests agreed: `respx` (async httpx mocking) or `httpretty`
- [ ] **H3.** E2E test scope agreed: what constitutes a passing E2E test for F2? (Submit real URL vs mock backend?)
- [ ] **H4.** Minimum pipeline test coverage agreed: 80% line coverage on `url_extractor.py`, `status_formatter.py`, `report_formatter.py`

---

### Section I: Outstanding Decisions Required from Project Owner

- [ ] **I1.** **DATABASE CHOICE**: OpenWebUI conversation history — SQLite (simple) or Supabase PostgreSQL (integrated)?
- [ ] **I2.** **OPENWEBUI VERSION**: Specific version tag to use (e.g., `v0.6.x`) — confirm against Pipelines compatibility matrix
- [ ] **I3.** **USER REGISTRATION**: Confirm `ENABLE_SIGNUP=false` (admin-only user creation) as the v1.0 policy
- [x] **I4.** **RATE LIMITING** — RESOLVED: M9.2 (Rate Limiting) is not yet implemented. Pipeline handles 429 as an error condition (`rate_limited` ErrorCard). No M9.2 dependency for F1–F4. F1 may proceed before M9.2 is complete.
- [ ] **I5.** **CONCURRENT JOBS**: `MAX_CONCURRENT_JOBS=4` in backend settings. Should the pipeline warn users when the server is at capacity before submitting, or only after receiving a 429?
- [ ] **I6.** **REPORT HISTORY OWNERSHIP**: Is it acceptable at v1.0 for report history to live in OpenWebUI's database rather than ArchMind's Supabase? If not, a custom history page must be planned in F3.

---

### Section J: Phase 0 Sign-Off

- [ ] **J1.** All architectural decisions (ADR-F001 through ADR-F008) are reviewed and accepted
- [ ] **J2.** All ASCII wireframes are reviewed and accepted as the design target
- [ ] **J3.** All UX decisions (Section 5) are reviewed and accepted
- [ ] **J4.** Branding guide (Section 6) is reviewed and accepted
- [ ] **J5.** Component inventory (Section 7) is reviewed and complete
- [ ] **J6.** Frontend folder architecture (Section 8) is reviewed and accepted
- [ ] **J7.** Revised F1–F5 roadmap (Section 9) is reviewed and accepted
- [ ] **J8.** All Section I outstanding decisions are resolved
- [ ] **J9.** All Section A–H checklist items are resolved
- [ ] **J10.** Phase 0 document is committed to version control

**Phase 0 is complete when all Section J items are checked.**

---

*Document version: 1.0*  
*Author: ArchMind AI Engineering*  
*Status: Awaiting Phase 0 sign-off (Section J)*
