# ArchMind AI — Product Roadmap to v1.0

**Role**: Principal Software Architect & Product Lead  
**Date**: 2026-07-15  
**Scope**: Current repository state → production-ready v1.0  
**Constraint**: No redesign. Extend the existing FastAPI + LangGraph + Qdrant + Gemini + Supabase architecture only.

---

## Current State Snapshot

| Area | Status | Evidence |
|---|---|---|
| LangGraph 8-node pipeline | **Complete** | Phases 1–8 committed and tested |
| FastAPI gateway (5 endpoints) | **Complete** | `api/main.py`, `api/routers/` |
| Supabase persistence (jobs + reports) | **Complete** | `scripts/supabase_schema.sql` |
| Qdrant RAG retrieval | **Complete** | `rag/`, `services/rag_agent/` |
| Gemini generation + embeddings | **Complete** | `infrastructure/gemini_client.py` |
| Structured logging | **Complete** | `shared/logging/logger.py` |
| Test suite | **Complete** | 385 tests, all passing |
| **Frontend UI** | **Missing** | No `frontend/` directory exists |
| **API authentication** | **Missing** | All endpoints are open, no auth middleware |
| **Rate limiting** | **Missing** | No request throttling of any kind |
| **Docker / Docker Compose** | **Missing** | No Dockerfile, no docker-compose.yml |
| **CI/CD pipeline** | **Missing** | No `.github/workflows/` directory |
| **Knowledge base depth** | **Thin** | Only 4 markdown files loaded into Qdrant |
| **Monitoring / metrics** | **Missing** | Structured logs only; no Prometheus, no traces |
| **Production deployment** | **Missing** | Manual only; no cloud target configured |

### Known Codebase Gaps (pre-v1.0 fixes required)

| Gap | Location | Impact |
|---|---|---|
| `MAX_CLONE_TIMEOUT_SECONDS` defined in `Settings` but hardcoded 120 s in `IngestionService` | `config/settings.py`, `services/ingestion/ingestion_service.py` | Setting has no effect; misconfiguration is silent |
| CORS `allow_origins` currently reads from `settings.cors_origins` — must be locked to production domain before go-live | `api/main.py` | Permissive CORS in prod leaks API to arbitrary browser clients |
| Concurrent job cap is enforced only inside `AnalysisOrchestrator`; API layer returns 202 before checking capacity | `api/routers/jobs.py`, `services/orchestrator/orchestrator_service.py` | Client must poll to discover rejection; 429 at submission would be cleaner |
| Orchestrator comment: "In-flight jobs are lost if the API process restarts. Suitable for MVP." | `services/orchestrator/orchestrator_service.py` | Known; `recover_orphaned_jobs()` mitigates on restart but in-flight work is still lost |

---

## Overall Progression Table

```
Current State (Phase 8 done)
        │
        ▼
Phase 9:  API Security & Rate Limiting          ← Backend
        │
        ▼
Phase 10: Knowledge Base Expansion              ← AI / RAG
        │
        ▼
Phase 11: Frontend UI                           ← Product (largest phase)
        │
        ▼
Phase 12: Containerization & Local Dev          ← Infrastructure
        │
        ▼
Phase 13: CI/CD Pipeline                        ← Infrastructure
        │
        ▼
Phase 14: Production Deployment                 ← Deployment
        │
        ▼
Phase 15: Monitoring & Observability            ← Operations
        │
        ▼
Phase 16: Production Hardening                  ← Backend + Infra
        │
        ▼
        v1.0 Release
```

---

## MoSCoW Classification Overview

| Classification | Phases |
|---|---|
| **Must Have** (v1.0 blockers) | 9, 10, 11, 12, 13, 14 |
| **Should Have** (v1.0 quality) | 15, 16 |
| **Nice to Have** (v1.0 polish) | See section below |
| **Future v1.1+** | See section below |

---

## Phase Roadmap

---

### Phase 9 — API Security & Rate Limiting

**Goal**: Secure the public API surface before any external exposure.  
**MoSCoW**: Must Have  
**Complexity**: Medium  
**Required for v1.0**: Yes

**Why it is needed**:  
Every endpoint is currently open with no authentication and no request throttling. Deploying the existing backend to a public URL as-is would allow any actor to submit unlimited analysis jobs, exhaust Gemini API quota, overload the single-process orchestrator, and cause denial of service. This phase is a hard blocker for all subsequent phases that assume a secured API.

**Dependencies**: None. Pure backend extension on top of Phase 8.

**Risks**:
- Rate limit tuning: too aggressive blocks legitimate users; too permissive fails to protect
- API key distribution: must decide whether keys are issued manually (MVP) or via a registration flow (v1.1)
- Middleware ordering matters — auth must run before rate limiting

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M9.1 | Static API key authentication middleware | All endpoints except `/health` return 401 without valid `X-API-Key` header. `/health` remains unauthenticated. Unit tests cover valid key, missing key, wrong key. | Backend |
| M9.2 | Per-IP rate limiting | POST `/jobs` limited to 10 req/min per IP. GET endpoints limited to 60 req/min per IP. Returns 429 with `Retry-After` header on breach. | Backend |
| M9.3 | Concurrent job capacity enforcement at API layer | POST `/jobs` returns 429 with `detail: "Server at capacity"` immediately when `MAX_CONCURRENT_JOBS` is reached, rather than accepting then silently dropping. | Backend |
| M9.4 | CORS policy hardening | `cors_origins` setting validated to reject wildcard `*` in production mode. Test confirms CORS headers match configured origin only. | Backend, Config |
| M9.5 | Security regression tests | Integration tests cover: no-auth 401, wrong-key 401, valid-key 200, rate limit 429, capacity 429, health unauthenticated 200. | Backend, Tests |

---

### Phase 10 — Knowledge Base Expansion

**Goal**: Bring the RAG knowledge base from prototype depth (4 documents) to production coverage.

**MoSCoW**: Must Have  
**Complexity**: Medium  
**Required for v1.0**: Yes

**Why it is needed**:  
The RAG pipeline (`RAGRetrievalNode`, `RecommendationNode`) is complete and performing correctly. However, the knowledge base currently contains only 4 markdown files covering 2 topics. The quality of AI-generated recommendations is bounded by knowledge base coverage. With only 4 documents, the majority of queries will find no relevant chunks above the 0.72 cosine similarity threshold, producing generic recommendations. This is the primary driver of output quality at v1.0.

**Dependencies**: Phase 9 (API secured before expanding capabilities that consume AI quota).

**Risks**:
- Content quality: poorly written documents produce hallucinated or misleading recommendations
- Chunk boundary problems: documents that are poorly structured will split badly under the 1500-char/150-overlap chunker
- RAG recall degradation if too many low-quality documents dilute the embedding space
- Ingest script failures leave partial state in Qdrant

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M10.1 | Architecture pattern library expansion | 10+ curated documents covering: Hexagonal, Clean Architecture, CQRS, Event-Driven, Service Mesh, API Gateway, Saga, Strangler Fig, BFF, Sidecar. Each doc has clear header structure for chunk splitting. | AI, Docs |
| M10.2 | Security pattern library expansion | 10+ curated documents covering: OWASP Top 10 expanded (A01–A10), secrets management, dependency scanning, JWT best practices, CORS hardening, CSP, SQL injection patterns, XSS, SSRF, container security. | AI, Docs |
| M10.3 | RAG quality validation suite | Automated tests assert that known queries (e.g., "LAYERED architecture with SQL injection risk") retrieve ≥ 3 relevant chunks above threshold. Recall measured against a fixed query set. | AI, Tests |
| M10.4 | Knowledge base ingest CLI script | `python -m rag.ingest` script loads all `knowledge_base/` markdown files into Qdrant, reports chunk count per file, skips existing chunks (idempotent), exits non-zero on connection failure. | AI, Infra |

---

### Phase 11 — Frontend UI

**Goal**: Build a web UI that makes ArchMind AI accessible to non-technical users.

**MoSCoW**: Must Have  
**Complexity**: High  
**Required for v1.0**: Yes

**Why it is needed**:  
ArchMind AI is currently a backend service only. Without a UI, it is a developer-only tool accessible only via raw HTTP clients. A v1.0 product release requires an interface that a software engineering team member can open in a browser, submit a GitHub repository URL, and view a rendered analysis report. This is the largest remaining phase by scope.

**Dependencies**: Phase 9 (auth) — the UI must pass authentication credentials to the API. Phase 10 (KB quality) — demo quality depends on KB depth.

**Risks**:
- New technology layer with the most unknowns (frontend stack choice, build tooling, SSR vs SPA)
- Markdown-to-HTML rendering for large reports must handle code blocks, tables, headings correctly
- Job polling UX: must communicate async status clearly without overloading the API
- Mobile layout for a complex markdown report is non-trivial

**Technology recommendation**: Next.js 14+ (App Router) with Tailwind CSS. Rationale: SSR for initial report page (SEO + performance), API route proxy for CORS isolation, Tailwind for rapid styling, broad community support. This is a recommendation; implementation choice is yours.

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M11.1 | Project scaffold | Next.js app created at `frontend/`. ESLint, Prettier, TypeScript strict mode configured. `npm run dev` starts without errors. | Frontend |
| M11.2 | Submit job page | Form accepts GitHub HTTPS URL. Client-side validation mirrors backend rules (https://github.com/ prefix). On submit: calls POST `/api/v1/jobs`, transitions to status page on 202. Shows error message on 400/429/401. | Frontend |
| M11.3 | Job status polling page | Polls GET `/api/v1/jobs/{id}` every 5 s. Shows status (PENDING / RUNNING / COMPLETE / FAILED) with visual indicator. On COMPLETE: navigates to report page. On FAILED: shows `error_message`. Auto-stops polling after 30 min or on terminal status. | Frontend |
| M11.4 | Report viewer | Renders `markdown_content` as styled HTML (react-markdown or similar). Sections displayed in order from `sections[]`. Metadata panel shows: primary language, architecture pattern, confidence, finding counts, recommendation count. Copy-to-clipboard for raw markdown. | Frontend |
| M11.5 | Mobile-responsive layout | All pages usable on 375 px viewport (iPhone SE). Report markdown readable on mobile. Navigation accessible on mobile. Tested at 375/768/1280 px breakpoints. | Frontend |
| M11.6 | API client integration | `frontend/lib/api.ts` typed API client wraps all 5 backend endpoints. API key injected from environment variable (`NEXT_PUBLIC_API_KEY` or server-side only). No fetch calls outside the client module. | Frontend, Backend |
| M11.7 | Frontend tests | Vitest unit tests for URL validation logic. Playwright or Cypress E2E test: submit → poll → view report (against mocked API). | Frontend, Tests |

---

### Phase 12 — Containerization & Local Dev

**Goal**: Package every service component as a Docker container; provide a single-command local development environment.

**MoSCoW**: Must Have  
**Complexity**: Low  
**Required for v1.0**: Yes

**Why it is needed**:  
There is currently no reproducible way to run ArchMind AI locally without manually installing Qdrant, configuring Python, building the RAG knowledge base, and writing `.env` files. Contributors cannot onboard without detailed manual steps. Production deployments require containers. CI/CD requires containers. This phase unblocks both.

**Dependencies**: Phase 11 (both backend and frontend services must exist before writing their Dockerfiles).

**Risks**:
- `git clone` inside the backend container (IngestionService) requires `git` available at runtime — must be included in the image
- Tree-sitter grammars install native extensions — multi-stage build must include build tools
- Qdrant data volume persistence strategy must be decided (named volume vs bind mount)

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M12.1 | Backend Dockerfile | Multi-stage build: builder stage installs deps; runtime stage is minimal. Image runs `uvicorn api.main:create_app --factory`. `git` and `tree-sitter` compile correctly in container. Image size < 600 MB. | Infra |
| M12.2 | Frontend Dockerfile | Multi-stage: node builder → nginx static server (or Next.js standalone). `npm run build` succeeds inside container. | Infra, Frontend |
| M12.3 | `docker-compose.yml` | Services: `api` (backend), `frontend`, `qdrant` (official image). API mounts `.env` from project root. Qdrant uses named volume for persistence. `docker compose up` starts all 3 services. Health check passes at `http://localhost:3000`. | Infra |
| M12.4 | `.dockerignore` files | Both `backend/.dockerignore` and `frontend/.dockerignore` exclude: `.env`, `__pycache__`, `.git`, `node_modules`, test files. Confirmed by inspecting image layer contents. | Infra |
| M12.5 | Updated local setup docs | README Quick Start section updated to: `docker compose up` as primary path. Manual Python path retained as secondary. | Docs |

---

### Phase 13 — CI/CD Pipeline

**Goal**: Automate test, lint, build, and deploy on every pull request and main branch push.

**MoSCoW**: Must Have  
**Complexity**: Medium  
**Required for v1.0**: Yes

**Why it is needed**:  
There is currently no automation preventing a broken commit from reaching `main`. With a growing codebase and an upcoming frontend, manual verification is not sustainable. CI is the minimum safety net for a production project.

**Dependencies**: Phase 12 (containers required for CI builds).

**Risks**:
- Gemini API calls in workflow: tests that call Gemini must be skipped in CI or use mocks (most existing tests already use mocks — verify this)
- Supabase in CI: integration tests that require live Supabase need a test project or must be skipped
- GitHub Actions minutes cost if workflow is slow — optimize test parallelism

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M13.1 | Backend PR validation workflow | `.github/workflows/backend-ci.yml`: runs on PR to `main`. Steps: `pip install -r requirements-dev.txt`, `ruff check`, `mypy`, `pytest`. Fails PR if any step is non-zero. Runtime < 3 min. | Infra, Backend |
| M13.2 | Frontend PR validation workflow | `.github/workflows/frontend-ci.yml`: runs on PR to `main`. Steps: `npm ci`, `eslint`, `tsc --noEmit`, `vitest run`. Fails PR if any step is non-zero. | Infra, Frontend |
| M13.3 | Docker build validation | Both Dockerfiles build successfully in CI on every PR (no push, just build). Catches Dockerfile regressions before merge. | Infra |
| M13.4 | Staging deploy workflow | `.github/workflows/deploy-staging.yml`: triggers on push to `main`. Builds and pushes Docker images to registry. Deploys to staging environment. Smoke-tests `/health` endpoint. | Infra, Deployment |
| M13.5 | Test coverage gate | pytest-cov configured with 80% minimum line coverage gate. CI fails if coverage drops below threshold. Coverage report uploaded as artifact. | Backend, Tests |

---

### Phase 14 — Production Deployment

**Goal**: Stand up a live, publicly accessible production environment.

**MoSCoW**: Must Have  
**Complexity**: High  
**Required for v1.0**: Yes

**Why it is needed**:  
v1.0 requires a running product. This phase provisions all infrastructure, loads the knowledge base, configures production secrets, and validates the end-to-end system under real conditions.

**Dependencies**: Phases 12, 13 (containers + CI required before any deploy target).

**Risks**:
- Cloud provider selection locks in operational model (cost, egress, container support)
- Qdrant persistence: managed cloud (Qdrant Cloud) vs self-hosted; self-hosted requires volume management
- Secrets management: API keys (Gemini, Supabase) must never appear in container images or CI logs
- Cold-start latency: first job after deploy exercises full pipeline including git clone — may be slow
- Cost unpredictability if repository analysis jobs are long-running and Gemini token usage is high

**Recommended deployment targets** (choose one):
- **Railway**: simplest for FastAPI + Next.js + Qdrant; built-in secrets, volume support, auto-deploy from GitHub
- **Fly.io**: more control, better Qdrant volume support, slightly higher ops complexity
- **AWS ECS + ECR**: most enterprise-ready, most complex, most expensive

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M14.1 | Cloud provider provisioned | Account created, billing configured, project created. Backend and frontend services deployed from Docker images. Both accessible via HTTPS. | Deployment |
| M14.2 | Production Supabase project | Separate Supabase project for production (not dev project). Schema applied from `supabase_schema.sql`. RLS policies reviewed. Supabase URL and key stored as deployment secrets. | Deployment, Backend |
| M14.3 | Qdrant production instance | Qdrant Cloud or self-hosted with persistent volume. Collection created with correct vector dimensions (3072). Connection tested from backend container. | Deployment, AI |
| M14.4 | Knowledge base loaded to production | `python -m rag.ingest` run against production Qdrant. All Phase 10 documents indexed. Chunk count logged and verified. Spot-check: 3 sample queries return relevant results. | Deployment, AI |
| M14.5 | Production secrets configured | All secrets (GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY, API keys) stored in provider secrets manager. No secrets in environment files committed to repo. `.env.example` kept current. | Deployment |
| M14.6 | Custom domain + TLS | Custom domain configured. HTTPS enforced. CORS `allow_origins` locked to production domain. | Deployment, Backend |
| M14.7 | End-to-end smoke test | Submit a real public GitHub repository via the production UI. Verify: job transitions PENDING → RUNNING → COMPLETE, report renders correctly, all 6 sections present, metadata populated. | Deployment, All |

---

### Phase 15 — Monitoring & Observability

**Goal**: Add production-grade visibility into system health, error rates, and job performance.

**MoSCoW**: Should Have  
**Complexity**: Medium  
**Required for v1.0**: No (but strongly recommended before user traffic)

**Why it is needed**:  
Structured logging exists but provides no aggregation, alerting, or time-series visibility. Without metrics, production incidents are discovered by users before operators. A single Prometheus endpoint and basic alerting is the minimum viable observability setup.

**Dependencies**: Phase 14 (production environment must exist to monitor).

**Risks**:
- Adding Prometheus middleware adds latency measurement overhead — negligible at this traffic scale
- Log aggregation vendor lock-in (Datadog, Grafana Cloud, etc.) — use provider's native logging first

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M15.1 | Prometheus metrics endpoint | `GET /metrics` returns Prometheus text format. Metrics include: `archmind_jobs_submitted_total`, `archmind_jobs_completed_total`, `archmind_jobs_failed_total`, `archmind_job_duration_seconds` (histogram), `archmind_http_requests_total` (by route + status). | Backend |
| M15.2 | Structured log aggregation | Production logs ship to cloud provider's log viewer or external aggregator. Logs queryable by `job_id`, `status`, `error_type`. Log retention ≥ 30 days. | Deployment |
| M15.3 | Basic alerting | Alert fires when: error rate > 5% over 5 min, no jobs completing in 30 min during business hours, health endpoint returning non-200. Alert delivered to email or Slack. | Deployment |
| M15.4 | Health dashboard | Simple Grafana or provider-native dashboard showing: request rate, error rate, job completion rate, p95 job duration, dependency status (Gemini/Qdrant/Supabase). | Deployment |

---

### Phase 16 — Production Hardening

**Goal**: Fix known codebase gaps, improve reliability, and close operational risks before sustained user traffic.

**MoSCoW**: Should Have  
**Complexity**: Low–Medium  
**Required for v1.0**: No (but clears known technical debt before it becomes a production incident)

**Why it is needed**:  
Several known gaps (documented in the codebase itself) are acceptable for MVP but are reliability risks under production load. This phase closes them systematically.

**Dependencies**: Phase 14 (deployed system surfaces real failure modes).

**Risks**:
- Job cancellation (M16.2) requires careful orchestrator state management — cancelling a mid-flight LangGraph run that is inside a git clone or Gemini call requires cooperative cancellation, not force-kill
- `MAX_CLONE_TIMEOUT_SECONDS` wiring (M16.1) is a low-risk change but must be covered by a test

| Milestone | Objective | Acceptance Criteria | Areas Affected |
|---|---|---|---|
| M16.1 | Wire `MAX_CLONE_TIMEOUT_SECONDS` from settings | `IngestionService` reads `settings.max_clone_timeout_seconds` instead of hardcoding 120 s. Unit test confirms timeout value is respected. Setting documented in `.env.example`. | Backend, Config |
| M16.2 | Job cancellation endpoint | `DELETE /api/v1/jobs/{job_id}` cancels a PENDING or RUNNING job. PENDING jobs: mark FAILED immediately. RUNNING jobs: signal orchestrator to abort after current node completes. Returns 200 on success, 404 if not found, 409 if already terminal. | Backend |
| M16.3 | Repository size pre-check | Before `git clone`, validate repository size via GitHub API (public repos expose `size` in `/repos/{owner}/{repo}`). Reject immediately with 422 if size exceeds `MAX_REPO_SIZE_MB`. Avoids wasting clone time and disk on oversized repos. | Backend, AI |
| M16.4 | Graceful shutdown on SIGTERM | On SIGTERM: stop accepting new jobs, allow in-flight jobs to complete (up to 60 s timeout), then exit. `shutdown_executor()` already exists — wire it to SIGTERM handler. | Backend |
| M16.5 | Memory and disk cleanup | Cloned repositories are deleted after analysis (`ingestion_service.py` likely does this — verify). Add cleanup in `finally` block to guarantee deletion even on exception. Add disk usage log line. | Backend |

---

## Nice to Have (v1.0 polish, not blockers)

These items improve the product experience at v1.0 but are not required for a functional, secure, deployed release.

| Item | Description | Effort |
|---|---|---|
| Report export to PDF | Browser-side PDF export of the rendered report using `window.print()` or a library | Low |
| Dark mode UI | Tailwind `dark:` class support toggled by system preference | Low |
| Job history page | List of past analysis jobs with status and links to reports | Medium |
| Shareable report URL | Permanent public URL for a report that can be shared without auth | Medium |
| Estimated completion time | Show estimated remaining time on job status page based on historical durations | Medium |
| Retry failed jobs | Button on failed job page to resubmit the same URL | Low |

---

## Future v1.1+ (out of v1.0 scope)

| Feature | Rationale for deferral |
|---|---|
| GitHub App / Webhook integration | Requires OAuth app registration, GitHub event handling, and webhook security — separate product surface |
| Multi-user authentication (OAuth2) | Requires user model, sessions, token management — significant scope; v1.0 uses static API keys |
| Distributed job queue (Redis + RQ or Celery) | Orchestrator comment explicitly scopes this to scale-out; single-instance is correct for MVP |
| Multi-LLM backend | Gemini is the only supported model; abstraction layer (LiteLLM) adds complexity without v1.0 value |
| GitLab / Bitbucket support | `SubmitJobRequest` validates `https://github.com/` only; extending requires parser and clone path changes |
| Real-time job progress via WebSocket | SSE or WebSocket for streaming node-by-node progress; polling is sufficient for MVP |
| Custom RAG threshold configuration | Per-request override of `RAG_RELEVANCE_THRESHOLD`; currently a constant — adds API surface complexity |
| Report comparison (diff between two analyses) | Requires storing multiple reports per repo, diff algorithm — significant feature scope |
| Team workspaces | Multi-user collaboration, shared job history, team API keys — full SaaS product scope |

---

## Phase Execution Summary

| Phase | Title | MoSCoW | Complexity | Affected Areas | v1.0 Blocker |
|---|---|---|---|---|---|
| **9** | API Security & Rate Limiting | Must Have | Medium | Backend | **Yes** |
| **10** | Knowledge Base Expansion | Must Have | Medium | AI, Docs | **Yes** |
| **11** | Frontend UI | Must Have | High | Frontend, Backend | **Yes** |
| **12** | Containerization & Local Dev | Must Have | Low | Infra | **Yes** |
| **13** | CI/CD Pipeline | Must Have | Medium | Infra | **Yes** |
| **14** | Production Deployment | Must Have | High | Deployment, All | **Yes** |
| **15** | Monitoring & Observability | Should Have | Medium | Backend, Deployment | No |
| **16** | Production Hardening | Should Have | Low–Medium | Backend, Infra | No |

**Total Must Have phases**: 6  
**Estimated critical path**: Phase 9 → 10 → 11 → 12 → 13 → 14 (sequential; each has dependency on predecessor)  
**Phases that can run in parallel**: Phase 10 and Phase 11 are independent once Phase 9 is done. Phase 15 and Phase 16 are independent once Phase 14 is done.

---

## Recommended Next Phase: Phase 9 — API Security & Rate Limiting

**Recommendation: Start Phase 9 immediately.**

**Justification**:

1. **Blocking dependency for everything downstream.** Phase 11 (UI) needs to know the auth model before building the API client. Phase 14 (deployment) cannot go live with an open API. Phase 13 (CI) needs the security test suite to exist. Phase 9 is the root node of the remaining dependency graph.

2. **Shortest, most bounded phase on the critical path.** Milestones M9.1–M9.5 are pure backend additions with no new infrastructure, no new language, and no design uncertainty. The API surface is already defined. This phase can realistically be completed in 3–5 days of focused work.

3. **High leverage per effort unit.** One middleware layer (auth) and one rate limiter protects all 5 existing endpoints simultaneously. The security regression test suite (M9.5) then runs in CI for every subsequent phase automatically.

4. **Prevents a bad deployment pattern.** If Phase 11 (UI) were attempted first, the UI would be built against an open API. Retrofitting auth into both the UI and backend after the UI is complete is more expensive than wiring auth first and building the UI with auth from day one.

5. **Forces one architectural decision early (API key distribution model)** that must be resolved before building the user registration or onboarding flow. Making this decision at Phase 9 rather than Phase 14 prevents a late-stage rework.

**What Phase 10 (KB Expansion) should run in parallel with Phase 11**: Once Phase 9 is done, knowledge base content work (Phase 10) requires no engineering implementation — it is content creation and ingest scripting. It can proceed in parallel with frontend engineering (Phase 11). The frontend does not depend on KB quality, but the Phase 14 smoke test does.
