-- ArchMind AI — Supabase schema
--
-- Tables:
--   jobs    — job lifecycle records (created by Job Manager, updated by PersistenceNode)
--   reports — final assembled reports (written by PersistenceNode via upsert)
--
-- Column naming mirrors the Pydantic models in shared/types/job_types.py
-- and shared/types/report_types.py exactly. Do not rename columns without
-- also updating the corresponding model fields and SupabaseClient queries.
--
-- Run order: jobs first (reports has a FK to jobs).

-- ---------------------------------------------------------------------------
-- jobs
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS jobs (
    job_id          UUID        PRIMARY KEY,
    repo_url        TEXT        NOT NULL,
    repo_name       TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'PENDING',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_version  TEXT        NOT NULL DEFAULT '1.0',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    report_id       UUID,
    error_message   TEXT,
    error_type      TEXT,

    CONSTRAINT jobs_status_check CHECK (
        status IN ('PENDING', 'RUNNING', 'COMPLETE', 'FAILED')
    ),
    CONSTRAINT jobs_complete_requires_report CHECK (
        status != 'COMPLETE' OR report_id IS NOT NULL
    ),
    CONSTRAINT jobs_failed_requires_error CHECK (
        status != 'FAILED' OR (error_message IS NOT NULL AND error_message != '')
    )
);

CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs (status);
CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs (created_at DESC);

-- ---------------------------------------------------------------------------
-- reports
-- ---------------------------------------------------------------------------
-- metadata and sections are stored as JSONB to avoid schema churn as
-- report content evolves. The Pydantic model enforces structure in-process.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reports (
    report_id           UUID        PRIMARY KEY,
    job_id              UUID        NOT NULL REFERENCES jobs (job_id) ON DELETE CASCADE,
    repo_url            TEXT        NOT NULL,
    repo_name           TEXT        NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL,
    schema_version      TEXT        NOT NULL DEFAULT '1.0',
    markdown_content    TEXT        NOT NULL,
    metadata            JSONB       NOT NULL,
    sections            JSONB       NOT NULL
);

CREATE INDEX IF NOT EXISTS reports_job_id_idx ON reports (job_id);
CREATE INDEX IF NOT EXISTS reports_generated_at_idx ON reports (generated_at DESC);
