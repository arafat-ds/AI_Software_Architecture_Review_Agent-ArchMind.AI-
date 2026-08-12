# ArchMind Backend API Contract (Frontend / Pipeline View)

**Status:** Production Specification — v1.0
**Document owner:** Frontend / Pipeline Engineer
**Last updated:** 2026-08-10
**Canonical source:** `backend/api/` — schemas and routers
**Prerequisite for:** F2 implementation of `archmind_client.py`

This document is the pipeline engineer's reference for the ArchMind backend REST API. Every field, type, status code, and error shape is verified against the actual backend source code. Do not rely on assumptions — if a value is listed here, it comes from the implementation.

Relevant source files:

| File | Role |
|---|---|
| `backend/api/routers/health.py` | Health endpoint route |
| `backend/api/routers/jobs.py` | Job submission and status routes |
| `backend/api/routers/reports.py` | Report retrieval route |
| `backend/api/schemas/health_schemas.py` | `HealthResponse`, `DependencyStatus` |
| `backend/api/schemas/job_schemas.py` | `SubmitJobRequest`, `JobSubmittedResponse`, `JobStatusResponse` |
| `backend/api/schemas/report_schemas.py` | `ReportResponse`, `ReportMetadataResponse`, `ReportSectionResponse` |
| `backend/api/main.py` | Route wiring, CORS, auth dependency, global exception handler |
| `backend/api/security.py` | `require_auth`, `_check_api_key` |
| `backend/shared/types/enums.py` | `JobStatus`, `Severity`, `Confidence`, `ArchitecturePattern`, `SectionKey` |
| `backend/config/constants.py` | `REPORT_SCHEMA_VERSION`, `SECTION_ORDER` |

---

## Base URL and Authentication

### Base URL

Configured via the `ARCHMIND_API_URL` Valve (default: `http://backend:8000`).

All endpoints are under the `/api/v1` prefix as registered in `main.py`:

```
{ARCHMIND_API_URL}/api/v1/{endpoint}
```

### Authentication

All endpoints except `GET /api/v1/health` require the `X-API-Key` header.

| Header | Value |
|---|---|
| Name | `X-API-Key` |
| Value | The configured API key (≥ 32 characters, from Valves `ARCHMIND_API_KEY`) |

**Source:** `backend/api/security.py` — `APIKeyHeader(name="X-API-Key", auto_error=False)`

**Auth failure responses (both missing and invalid key return the same response — by design, to avoid leaking auth state):**

```
HTTP 401 Unauthorized
WWW-Authenticate: ApiKey realm="ArchMind AI"

{
  "detail": "Authentication required."
}
```

**Source:** `_AUTH_STATUS_CODE = 401`, `_AUTH_DETAIL = "Authentication required."`, `_AUTH_HEADERS = {"WWW-Authenticate": 'ApiKey realm="ArchMind AI"'}` in `security.py`.

### Global error format — 500

All unhandled server-side exceptions are caught by the global exception handler in `main.py` and return:

```
HTTP 500 Internal Server Error

{
  "detail": "Internal server error."
}
```

**Source:** `handle_unexpected_exception` in `backend/api/main.py`.

---

## Endpoint 1: GET /api/v1/health

### Summary

Returns the server's operational status and startup probe results for each external dependency.

### Authentication

**None required.** This endpoint is registered without `Depends(require_auth)` in `main.py`.

```python
app.include_router(health.router, prefix="/api/v1")  # no auth dependency
```

### Request

```
GET /api/v1/health
```

No request body. No query parameters.

### Success Response

```
HTTP 200 OK
Content-Type: application/json
```

**Response schema: `HealthResponse`**

| Field | Type | Always present | Description |
|---|---|---|---|
| `status` | `str` | Yes | Always `"ok"` when the server is accepting requests. Does **not** reflect dependency state. |
| `version` | `str` | Yes | Application version string. Currently `"1.0"` (from `REPORT_SCHEMA_VERSION` constant). |
| `dependencies` | `DependencyStatus` | Yes | Startup probe results for each external dependency. |
| `dependencies.gemini` | `str` | Yes | Gemini API probe result. |
| `dependencies.qdrant` | `str` | Yes | Qdrant probe result. |
| `dependencies.supabase` | `str` | Yes | Supabase probe result. |

**`status` is always `"ok"` at HTTP 200.** The server returns HTTP 200 even when dependencies are degraded. Degraded state is expressed only in the `dependencies` object, not in `status` or the HTTP code.

**Dependency status values** (all three fields use the same value set):

| Value | Meaning |
|---|---|
| `"ok"` | Probe succeeded at startup |
| `"failed"` | Probe attempt completed but returned an error |
| `"unreachable"` | Connection to the dependency could not be established |
| `"collection_missing"` | Qdrant only: server reachable but the knowledge base collection is not loaded |
| `"unknown"` | Probe has not run yet (server starting up, or running without lifespan in tests) |

**Source:** `backend/api/schemas/health_schemas.py` — `DependencyStatus` docstring.

### Example — all healthy

```json
{
  "status": "ok",
  "version": "1.0",
  "dependencies": {
    "gemini": "ok",
    "qdrant": "ok",
    "supabase": "ok"
  }
}
```

### Example — Qdrant collection not loaded

```json
{
  "status": "ok",
  "version": "1.0",
  "dependencies": {
    "gemini": "ok",
    "qdrant": "collection_missing",
    "supabase": "ok"
  }
}
```

### Example — Gemini unavailable

```json
{
  "status": "ok",
  "version": "1.0",
  "dependencies": {
    "gemini": "failed",
    "qdrant": "ok",
    "supabase": "ok"
  }
}
```

### Pipeline Integration

The pipeline calls `GET /api/v1/health` at startup (via `on_startup()`) to check dependency state. If any dependency is not `"ok"`, the `format_health_warning()` function (DependencyHealthBadge) prepends a warning block to the pipeline system prompt. This is an F4 feature.

**Fields consumed by pipeline:**
- `dependencies.gemini` — check for `"ok"` vs degraded
- `dependencies.qdrant` — check specifically for `"collection_missing"` (analysis will succeed but RAG quality will be lower)
- `dependencies.supabase` — check for `"ok"` vs degraded (FAILED means jobs cannot be persisted)

---

## Endpoint 2: POST /api/v1/jobs

### Summary

Submits a new analysis job. The backend creates the job record, queues it for execution, and returns immediately with the job ID. The analysis runs asynchronously.

### Authentication

Required. `X-API-Key` header.

### Request

```
POST /api/v1/jobs
Content-Type: application/json
X-API-Key: {ARCHMIND_API_KEY}
```

**Request schema: `SubmitJobRequest`**

| Field | Type | Required | Validation |
|---|---|---|---|
| `repo_url` | `str` | Yes | Must start with `"https://github.com/"`. Validated by `@field_validator("repo_url", mode="before")` in `SubmitJobRequest`. Trailing whitespace is stripped before validation. |

**Source:** `backend/api/schemas/job_schemas.py` — `SubmitJobRequest`.

### Example Request

```
POST /api/v1/jobs
Content-Type: application/json
X-API-Key: your-api-key-here

{
  "repo_url": "https://github.com/pallets/flask"
}
```

The `.git` suffix is accepted (e.g., `https://github.com/pallets/flask.git`) — the backend strips it when extracting `repo_name`.

### Success Response

```
HTTP 202 Accepted
Content-Type: application/json
```

**Response schema: `JobSubmittedResponse`**

| Field | Type | Description |
|---|---|---|
| `job_id` | `str` (UUID v4) | UUID of the newly created job. Use this to poll `GET /jobs/{job_id}`. |
| `status` | `str` | Always `"PENDING"` at creation time. |
| `message` | `str` | Always `"Analysis queued. Poll GET /jobs/{job_id} for status."` |

**Source:** `backend/api/routers/jobs.py` — `submit_job()`. `job_id` is generated with `uuid4()`.

### Example 202 Response

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "PENDING",
  "message": "Analysis queued. Poll GET /jobs/{job_id} for status."
}
```

### Error Responses

**401 — Missing or invalid API key:**

```json
{
  "detail": "Authentication required."
}
```

**422 — Invalid `repo_url` (does not start with `https://github.com/`):**

FastAPI wraps the Pydantic `field_validator` failure in a 422 response. The pipeline must treat this as a pipeline-side `invalid_url` error (the pipeline's URL extractor should prevent this from reaching the backend, but defensively handle it).

```
HTTP 422 Unprocessable Entity

{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "repo_url"],
      "msg": "Value error, repo_url must be a GitHub HTTPS URL starting with 'https://github.com/'.",
      "input": "https://gitlab.com/example/repo",
      "ctx": {
        "error": "repo_url must be a GitHub HTTPS URL starting with 'https://github.com/'."
      }
    }
  ]
}
```

**Note:** This is the FastAPI/Pydantic v2 422 format — a list in `detail`, not a string. The pipeline must not parse this detail structure — treat any 422 as `invalid_url` error type.

**429 — Rate limiting (NOT yet implemented):**

M9.2 (Rate Limiting) is not yet implemented. As of the current backend code, the `ThreadPoolExecutor` queues jobs when all `MAX_CONCURRENT_JOBS` slots are busy — it does not return 429. When M9.2 is implemented, the pipeline should treat 429 with `detail: "Server at capacity"` as the `rate_limited` error type. Pipeline must handle 429 defensively now even before M9.2 ships.

**500 — Unexpected backend error:**

```json
{
  "detail": "Internal server error."
}
```

### Pipeline Integration

On 202:
1. Extract `job_id` from response body.
2. Yield AnalysisHeader Phase 2 with the confirmed `job_id`.
3. Begin poll loop: `GET /api/v1/jobs/{job_id}`.

On 422: Yield `invalid_url` ErrorCard. Return from `pipe()`.
On 401: Yield configuration error (wrong API key in Valves). Return.
On 429: Yield `rate_limited` ErrorCard. Return.
On 5xx / connection error: Yield `service_unavailable` ErrorCard. Return (with retry logic per `PIPELINE_API_CONTRACT.md` Section 10).

---

## Endpoint 3: GET /api/v1/jobs/{job_id}

### Summary

Returns the current status of an analysis job. Poll this endpoint until the job reaches a terminal state (`COMPLETE` or `FAILED`).

### Authentication

Required. `X-API-Key` header.

### Request

```
GET /api/v1/jobs/{job_id}
X-API-Key: {ARCHMIND_API_KEY}
```

**Path parameter:**

| Parameter | Type | Validation |
|---|---|---|
| `job_id` | UUID | FastAPI validates path param format. A string that is not a valid UUID returns 422 before the route handler runs. |

**Source:** `backend/api/routers/jobs.py` — `get_job_status(job_id: UUID, ...)`.

### Success Response

```
HTTP 200 OK
Content-Type: application/json
```

**Response schema: `JobStatusResponse`**

| Field | Type | Nullable | Description |
|---|---|---|---|
| `job_id` | `str` (UUID) | No | Primary key of the job. |
| `repo_url` | `str` | No | Repository URL as submitted. |
| `repo_name` | `str` | No | Repository name extracted from the URL (`.git` suffix stripped). |
| `status` | `str` | No | Current lifecycle status. One of: `"PENDING"`, `"RUNNING"`, `"COMPLETE"`, `"FAILED"`. |
| `created_at` | `str` (ISO 8601, UTC) | No | Timestamp when the job was created. |
| `started_at` | `str` (ISO 8601, UTC) | **Yes** | Timestamp when the workflow began. `null` while `PENDING`. |
| `completed_at` | `str` (ISO 8601, UTC) | **Yes** | Timestamp when job reached terminal state. `null` while non-terminal. |
| `report_id` | `str` (UUID) | **Yes** | UUID of the generated report. `null` unless status is `"COMPLETE"`. |
| `error_message` | `str` | **Yes** | Human-readable error description. `null` unless status is `"FAILED"`. |
| `error_type` | `str` | **Yes** | Exception class name from the backend. `null` unless status is `"FAILED"`. |

**Source:** `backend/api/schemas/job_schemas.py` — `JobStatusResponse`.

### Job Lifecycle and Status Values

**Source:** `backend/shared/types/enums.py` — `JobStatus` enum and docstring.

```
PENDING → RUNNING → COMPLETE   (normal path)
PENDING → RUNNING → FAILED     (analysis error)
PENDING → FAILED               (validation failure before workflow starts)
```

| Status | Terminal? | `report_id` | `error_message` |
|---|---|---|---|
| `"PENDING"` | No | `null` | `null` |
| `"RUNNING"` | No | `null` | `null` |
| `"COMPLETE"` | **Yes** | **UUID string** | `null` |
| `"FAILED"` | **Yes** | `null` | **string** |

**`COMPLETE` and `FAILED` are the only terminal states. The pipeline must stop polling when either is received.**

### Example — job is PENDING

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "repo_url": "https://github.com/pallets/flask",
  "repo_name": "flask",
  "status": "PENDING",
  "created_at": "2026-08-10T14:22:01.123456Z",
  "started_at": null,
  "completed_at": null,
  "report_id": null,
  "error_message": null,
  "error_type": null
}
```

### Example — job is RUNNING

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "repo_url": "https://github.com/pallets/flask",
  "repo_name": "flask",
  "status": "RUNNING",
  "created_at": "2026-08-10T14:22:01.123456Z",
  "started_at": "2026-08-10T14:22:03.456789Z",
  "completed_at": null,
  "report_id": null,
  "error_message": null,
  "error_type": null
}
```

### Example — job is COMPLETE

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "repo_url": "https://github.com/pallets/flask",
  "repo_name": "flask",
  "status": "COMPLETE",
  "created_at": "2026-08-10T14:22:01.123456Z",
  "started_at": "2026-08-10T14:22:03.456789Z",
  "completed_at": "2026-08-10T14:22:48.789012Z",
  "report_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "error_message": null,
  "error_type": null
}
```

### Example — job FAILED

```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "repo_url": "https://github.com/owner/private-repo",
  "repo_name": "private-repo",
  "status": "FAILED",
  "created_at": "2026-08-10T14:22:01.123456Z",
  "started_at": "2026-08-10T14:22:03.456789Z",
  "completed_at": "2026-08-10T14:22:09.111213Z",
  "report_id": null,
  "error_message": "Repository clone failed — repository not found or is private.",
  "error_type": "GitCloneError"
}
```

### Error Responses

**401:** Same as all protected endpoints — `{"detail": "Authentication required."}`.

**404 — job_id not found:**

```json
{
  "detail": "Job 3fa85f64-5717-4562-b3fc-2c963f66afa6 not found."
}
```

**Source:** `raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")` in `jobs.py`.

**422 — job_id is not a valid UUID format:**

FastAPI validates the path parameter type before the handler runs. An invalid UUID string (e.g., `GET /jobs/not-a-uuid`) returns 422.

### Pipeline Integration

Poll this endpoint every `POLL_INTERVAL_SECONDS` seconds after receiving a `job_id` from `POST /jobs`.

On each 200 response:
- If `status` is `"PENDING"` or `"RUNNING"`: continue polling, yield a keepalive line.
- If `status` is `"COMPLETE"`: stop polling. Use `report_id` to call `GET /api/v1/reports/{report_id}`.
- If `status` is `"FAILED"`: stop polling. Yield a `job_failed` ErrorCard with `job_id` and `error_message`.

On 404: The job was created (202 was received) but the record cannot be found — this is an unexpected state. Yield `service_unavailable` ErrorCard.

Stop polling if elapsed wall-clock time exceeds `MAX_POLL_DURATION_SECONDS`. Yield `timeout` ErrorCard with `job_id`.

---

## Endpoint 4: GET /api/v1/reports/{report_id}

### Summary

Returns the completed analysis report. Call this only after `GET /jobs/{job_id}` returns `status: "COMPLETE"` with a non-null `report_id`.

**There is no `/api/v1/jobs/{job_id}/report` shortcut endpoint. The only report endpoint is `/api/v1/reports/{report_id}`.** The `report_id` UUID comes exclusively from the `JobStatusResponse.report_id` field.

### Authentication

Required. `X-API-Key` header.

### Request

```
GET /api/v1/reports/{report_id}
X-API-Key: {ARCHMIND_API_KEY}
```

**Path parameter:**

| Parameter | Type | Validation |
|---|---|---|
| `report_id` | UUID | FastAPI validates UUID format. Invalid format returns 422. |

**Source:** `backend/api/routers/reports.py` — `get_report(report_id: UUID, ...)`.

### Success Response

```
HTTP 200 OK
Content-Type: application/json
```

**Response schema: `ReportResponse`**

| Field | Type | Nullable | Description |
|---|---|---|---|
| `report_id` | `str` (UUID) | No | Primary key of the report. |
| `job_id` | `str` (UUID) | No | UUID of the job that produced this report. |
| `repo_url` | `str` | No | Repository URL that was analysed. |
| `repo_name` | `str` | No | Repository name. |
| `generated_at` | `str` (ISO 8601, UTC) | No | Timestamp when the report was generated. |
| `schema_version` | `str` | No | Report schema version. Currently `"1.0"`. |
| `markdown_content` | `str` | No | Full report content in Markdown. May be large (tens of KB for complex repositories). |
| `metadata` | `ReportMetadataResponse` | No | Structured analysis metadata. See below. |
| `sections` | `list[ReportSectionResponse]` | No | Ordered report sections. See below. |

**Source:** `backend/api/schemas/report_schemas.py` — `ReportResponse`.

---

### ReportMetadataResponse (nested in ReportResponse)

| Field | Type | Nullable | Possible values |
|---|---|---|---|
| `primary_language` | `str` | No | Language name as detected (e.g., `"Python"`, `"TypeScript"`) |
| `detected_architecture_pattern` | `str` | No | `"LAYERED"` \| `"MVC"` \| `"HEXAGONAL"` \| `"SERVICE_BASED"` \| `"MONOLITH_UNDIFFERENTIATED"` \| `"UNKNOWN"` |
| `architecture_confidence` | `str` | No | `"HIGH"` \| `"MEDIUM"` \| `"LOW"` |
| `security_finding_count` | `int` | No | Total security findings count. `0` when no findings. |
| `finding_counts_by_severity` | `dict` | No | Keys: `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"INFO"`. All five keys are **always present**; zero-count keys are never omitted. Values: `int` counts. |
| `highest_severity_finding` | `str` \| `null` | **Yes** | `"CRITICAL"` \| `"HIGH"` \| `"MEDIUM"` \| `"LOW"` \| `null`. **`null` when `security_finding_count` is 0.** |
| `recommendation_count` | `int` | No | Total recommendations count. |
| `p1_recommendation_count` | `int` | No | P1 (critical priority) recommendation count. |
| `rag_chunks_used_count` | `int` | No | RAG knowledge base chunks used in recommendations. |
| `analysis_duration_seconds` | `int` | No | Total workflow duration in seconds from job start to report completion. |
| `total_files_analyzed` | `int` | No | Source files analysed by the workflow. |
| `total_llm_tokens_used` | `int` | No | Total LLM tokens consumed across all generation calls. |

**Source:** `backend/api/schemas/report_schemas.py` — `ReportMetadataResponse`; `backend/shared/types/enums.py` — `ArchitecturePattern`, `Confidence`, `Severity`.

**Critical nullable field — `highest_severity_finding`:**

This field is `str | None` with `default=None`. When a repository has zero security findings, this field is `null` in the JSON response. The pipeline's MetadataCard renderer **must** handle `null` without crashing. Do not assume this field is always a string.

**Source:** `ReportMetadataResponse.highest_severity_finding: str | None = Field(default=None, ...)` in `report_schemas.py`. Internal type in `report_types.py` is `Severity | None` — serialized to string via `value.name` or `null`.

**`architecture_confidence` is a string, not a float.** Values are exactly `"HIGH"`, `"MEDIUM"`, or `"LOW"`. Do not expect a numeric confidence score (e.g., `0.91`).

**`finding_counts_by_severity` key presence:** All five severity keys (`"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"INFO"`) are **always present**, zero-initialized even when no findings exist. This is source-verified: `_compute_severity_counts()` in `security_service.py` initializes counts from `{level.name: 0 for level in Severity}` before iterating findings. `.get(key, 0)` style access remains safe but keys will never be absent.

---

### ReportSectionResponse (items in `sections[]`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `section_order` | `int` | No | Display order index, 1-based. |
| `section_key` | `str` | No | Section identifier. See canonical order below. |
| `section_title` | `str` | No | Human-readable section title for the TOC. |
| `content_markdown` | `str` | No | Section content in Markdown. |

**Source:** `backend/api/schemas/report_schemas.py` — `ReportSectionResponse`.

**Canonical section order** (from `backend/config/constants.py` — `SECTION_ORDER`):

| `section_order` | `section_key` |
|---|---|
| 1 | `"EXECUTIVE_SUMMARY"` |
| 2 | `"REPOSITORY_OVERVIEW"` |
| 3 | `"ARCHITECTURE_ASSESSMENT"` |
| 4 | `"SECURITY_FINDINGS"` |
| 5 | `"RECOMMENDATIONS"` |
| 6 | `"ACTIONABLE_NEXT_STEPS"` |

**Source:** `backend/config/constants.py` — `SECTION_ORDER` list and docstring: "Consumer rendering depends on this sequence. Do not reorder without a schema version bump."

The `sections[]` array is ordered by `section_order` ascending. The pipeline should render sections in the order they are returned — do not re-sort client-side.

---

### Example Success Response (abbreviated)

```json
{
  "report_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "repo_url": "https://github.com/pallets/flask",
  "repo_name": "flask",
  "generated_at": "2026-08-10T14:22:48.789012Z",
  "schema_version": "1.0",
  "markdown_content": "## ArchMind AI — Architecture Review\n\n...(full report Markdown)...",
  "metadata": {
    "primary_language": "Python",
    "detected_architecture_pattern": "LAYERED",
    "architecture_confidence": "HIGH",
    "security_finding_count": 3,
    "finding_counts_by_severity": {
      "CRITICAL": 0,
      "HIGH": 1,
      "MEDIUM": 2,
      "LOW": 0,
      "INFO": 0
    },
    "highest_severity_finding": "HIGH",
    "recommendation_count": 7,
    "p1_recommendation_count": 2,
    "rag_chunks_used_count": 12,
    "analysis_duration_seconds": 47,
    "total_files_analyzed": 214,
    "total_llm_tokens_used": 18440
  },
  "sections": [
    {
      "section_order": 1,
      "section_key": "EXECUTIVE_SUMMARY",
      "section_title": "Executive Summary",
      "content_markdown": "## Executive Summary\n\n..."
    },
    {
      "section_order": 2,
      "section_key": "REPOSITORY_OVERVIEW",
      "section_title": "Repository Overview",
      "content_markdown": "## Repository Overview\n\n..."
    }
  ]
}
```

### Example — no security findings (highest_severity_finding is null)

```json
{
  "metadata": {
    "security_finding_count": 0,
    "finding_counts_by_severity": {
      "CRITICAL": 0,
      "HIGH": 0,
      "MEDIUM": 0,
      "LOW": 0,
      "INFO": 0
    },
    "highest_severity_finding": null,
    ...
  }
}
```

### Error Responses

**401:** `{"detail": "Authentication required."}`

**404 — report_id not found:**

```json
{
  "detail": "Report a1b2c3d4-e5f6-7890-abcd-ef1234567890 not found."
}
```

**Source:** `raise HTTPException(status_code=404, detail=f"Report {report_id} not found.")` in `reports.py`.

**422 — invalid UUID format in path:** FastAPI path parameter validation failure.

### Pipeline Integration

Called once, after `GET /jobs/{job_id}` returns `status: "COMPLETE"` with a non-null `report_id`.

On 200:
1. Read `metadata` — render MetadataCard.
2. Read `sections[]` — render ReportTableOfContents from `section_title` values in `section_order` sequence.
3. Read `markdown_content` — stream in 512-character chunks as the report body.

On 404: Yield `service_unavailable` ErrorCard (the job completed but the report record is missing — unexpected state).

**`markdown_content` vs `sections[]`:** The pipeline uses `markdown_content` for the full streamed report body, and `sections[].section_title` for the TOC only. The `sections[].content_markdown` fields are not used separately at v1.0 — the full `markdown_content` is streamed as a single document.

---

## Additional Endpoint: GET /api/v1/jobs (list)

### Summary

Returns a list of all jobs, optionally filtered by status. **Not used by the pipeline at v1.0** but exists in the backend and may be useful for operator tooling.

### Authentication

Required.

### Request

```
GET /api/v1/jobs?status=PENDING
X-API-Key: {ARCHMIND_API_KEY}
```

Optional query parameter `status`: one of `PENDING`, `RUNNING`, `COMPLETE`, `FAILED`. If omitted, returns all jobs.

### Response

List of `JobStatusResponse` objects (same schema as `GET /jobs/{job_id}`).

---

## Polling Lifecycle — Complete Pipeline Contract

This section documents the exact sequence the pipeline follows from user input to report display.

```
1. User submits message in OpenWebUI
   → pipe() is called with user_message

2. Pipeline extracts GitHub URL from user_message
   → On failure: yield invalid_url ErrorCard → return

3. Pipeline yields AnalysisHeader Phase 1 (immediate, before any HTTP call):
   "## ArchMind AI — Submitting...\n\n**Repository:** {repo_name}\n"

4. Pipeline checks Valves:
   → ARCHMIND_API_KEY is empty: yield configuration error → return

5. POST {ARCHMIND_API_URL}/api/v1/jobs
   Body: {"repo_url": "{extracted_url}"}
   Header: X-API-Key: {ARCHMIND_API_KEY}

   → 202: extract job_id, proceed to step 6
   → 401: yield service_unavailable (wrong key) → return
   → 422: yield invalid_url ErrorCard → return
   → 429: yield rate_limited ErrorCard → return
   → 5xx / connection error: retry up to 2 times, then yield service_unavailable → return

6. Pipeline yields AnalysisHeader Phase 2 (only after 202 confirmed):
   "**Job ID:** `{job_id}`\n**Submitted:** {utc_timestamp}\n\n---\n"

7. Poll loop begins. On each cycle:
   a. Check elapsed time against MAX_POLL_DURATION_SECONDS
      → If exceeded: yield timeout ErrorCard (with job_id) → return

   b. GET {ARCHMIND_API_URL}/api/v1/jobs/{job_id}
      Header: X-API-Key: {ARCHMIND_API_KEY}

      → 200, status "PENDING" or "RUNNING":
            yield keepalive line: "⠸ Analysis running... ({elapsed}s)\n"
            wait POLL_INTERVAL_SECONDS
            continue loop

      → 200, status "COMPLETE":
            stop polling
            note report_id from response
            proceed to step 8

      → 200, status "FAILED":
            stop polling
            yield job_failed ErrorCard (with job_id and error_message)
            return

      → 404: yield service_unavailable ErrorCard → return
      → 5xx / connection error: retry up to 2 times, then yield service_unavailable → return

8. GET {ARCHMIND_API_URL}/api/v1/reports/{report_id}
   Header: X-API-Key: {ARCHMIND_API_KEY}

   → 200: proceed to step 9
   → 404: yield service_unavailable ErrorCard → return
   → 5xx: retry up to 2 times, then yield service_unavailable → return

9. Render report:
   a. yield MetadataCard Markdown (from response.metadata)
   b. yield ReportTableOfContents Markdown (from response.sections[].section_title, ordered by section_order)
   c. yield report body in 512-character chunks (from response.markdown_content)

10. Generator returns → stream closes → user sees complete response
```

---

## Pipeline Integration Contract Summary

Fields the pipeline **directly reads** from each endpoint response:

| Endpoint | Field | Used for |
|---|---|---|
| `GET /health` | `dependencies.gemini` | DependencyHealthBadge warning (F4) |
| `GET /health` | `dependencies.qdrant` | DependencyHealthBadge warning (F4) |
| `GET /health` | `dependencies.supabase` | DependencyHealthBadge warning (F4) |
| `POST /jobs` | `job_id` | AnalysisHeader Phase 2, poll loop, ErrorCards |
| `GET /jobs/{id}` | `status` | Determines continue/stop poll decision |
| `GET /jobs/{id}` | `report_id` | Passed to `GET /reports/{report_id}` on COMPLETE |
| `GET /jobs/{id}` | `error_message` | Included in `job_failed` ErrorCard |
| `GET /reports/{id}` | `metadata.primary_language` | MetadataCard row |
| `GET /reports/{id}` | `metadata.detected_architecture_pattern` | MetadataCard row (emoji prefix applied) |
| `GET /reports/{id}` | `metadata.architecture_confidence` | MetadataCard row |
| `GET /reports/{id}` | `metadata.security_finding_count` | MetadataCard row |
| `GET /reports/{id}` | `metadata.highest_severity_finding` | MetadataCard row — **null-safe access required** |
| `GET /reports/{id}` | `metadata.recommendation_count` | MetadataCard row |
| `GET /reports/{id}` | `metadata.p1_recommendation_count` | MetadataCard row |
| `GET /reports/{id}` | `metadata.rag_chunks_used_count` | MetadataCard row |
| `GET /reports/{id}` | `metadata.analysis_duration_seconds` | MetadataCard row |
| `GET /reports/{id}` | `metadata.total_files_analyzed` | MetadataCard row |
| `GET /reports/{id}` | `metadata.total_llm_tokens_used` | MetadataCard row |
| `GET /reports/{id}` | `sections[].section_title` | ReportTableOfContents |
| `GET /reports/{id}` | `sections[].section_order` | TOC ordering |
| `GET /reports/{id}` | `markdown_content` | Streamed report body (512-char chunks) |

Fields **not consumed** by the pipeline at v1.0 (present in response but ignored):

| Field | Reason |
|---|---|
| `JobStatusResponse.repo_url` | Pipeline already has it from user input |
| `JobStatusResponse.started_at`, `completed_at` | Not surfaced in pipeline output |
| `JobStatusResponse.error_type` | `error_message` is sufficient for ErrorCard |
| `ReportResponse.schema_version` | Not surfaced; informational only |
| `ReportResponse.generated_at` | Not surfaced at v1.0 |
| `ReportSectionResponse.section_key` | Not surfaced; `section_title` is used for TOC |
| `ReportSectionResponse.content_markdown` | Replaced by full `markdown_content` stream |
| `metadata.finding_counts_by_severity` | Not surfaced at v1.0 |

---

## Open Questions / F1 Verification Required

Only items that cannot be confirmed from current backend source code.

| # | Question | Impact if wrong | How to verify |
|---|---|---|---|
| OQ-1 | ~~Does `finding_counts_by_severity` always include all four severity keys, or only keys with non-zero counts?~~ **RESOLVED — source-verified.** All five severity keys (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`) are always present, zero-initialized. See `security_service.py:_compute_severity_counts()`. `.get(key, 0)` remains safe but keys are never absent. | — | — |
| OQ-2 | Are datetime fields in responses always UTC ISO 8601 with `Z` suffix, or may they include `+00:00` or be naive? | Pipeline display formatting | Run a job and inspect `created_at` field format |
| OQ-3 | What is the maximum realistic size of `markdown_content` in bytes? | Memory allocation per report; chunk count | Analyse a large repo (>500 files) and measure response body size |
| OQ-4 | When M9.2 (Rate Limiting) is implemented, what is the exact `detail` field value in the 429 response? | Pipeline must distinguish capacity 429 from other 429s | Verify when M9.2 is shipped |
| OQ-5 | Does `GET /api/v1/jobs` (list endpoint) require any specific pagination handling for large job lists? | Not a pipeline concern at v1.0 — only relevant for operator tooling | Review M9.x implementation when available |

---

## Appendix: Related Documents

| Document | Location |
|---|---|
| Pipeline API Contract | `frontend/docs/PIPELINE_API_CONTRACT.md` |
| Phase 0 Architecture | `frontend/docs/PHASE_0_ARCHITECTURE.md` |
| Backend settings | `backend/config/settings.py` |
| Backend job schemas | `backend/api/schemas/job_schemas.py` |
| Backend report schemas | `backend/api/schemas/report_schemas.py` |
| Backend health schemas | `backend/api/schemas/health_schemas.py` |
| Backend enum types | `backend/shared/types/enums.py` |
| Backend constants | `backend/config/constants.py` |
