/**
 * Deterministic mock API responses for tests and local development
 * without a running backend.
 */

import type {
  SubmitJobResponse,
  JobStatusResponse,
  ReportResponse,
} from "@/types/archmind";

export const MOCK_JOB_ID = "00000000-0000-0000-0000-000000000001";
export const MOCK_REPORT_ID = "00000000-0000-0000-0000-000000000002";

export const mockSubmitResponse: SubmitJobResponse = {
  job_id: MOCK_JOB_ID,
  status: "PENDING",
  message: "Job queued successfully",
};

export const mockJobPending: JobStatusResponse = {
  job_id: MOCK_JOB_ID,
  repo_url: "https://github.com/test/repo",
  repo_name: "test/repo",
  status: "PENDING",
  created_at: "2026-10-26T10:00:00Z",
  started_at: null,
  completed_at: null,
  report_id: null,
  error_message: null,
  error_type: null,
};

export const mockJobRunning: JobStatusResponse = {
  ...mockJobPending,
  status: "RUNNING",
  started_at: "2026-10-26T10:00:02Z",
};

export const mockJobComplete: JobStatusResponse = {
  ...mockJobRunning,
  status: "COMPLETE",
  completed_at: "2026-10-26T10:05:00Z",
  report_id: MOCK_REPORT_ID,
};

export const mockJobFailed: JobStatusResponse = {
  ...mockJobPending,
  status: "FAILED",
  error_message: "Repository clone failed: timeout after 120s",
  error_type: "IngestionError",
};

export const mockReport: ReportResponse = {
  report_id: MOCK_REPORT_ID,
  job_id: MOCK_JOB_ID,
  repo_url: "https://github.com/test/repo",
  repo_name: "test/repo",
  generated_at: "2026-10-26T10:05:00Z",
  schema_version: "1.0",
  markdown_content: "# test/repo Architecture Review\n\nFull report content.",
  metadata: {
    primary_language: "Python",
    detected_architecture_pattern: "Layered Architecture",
    architecture_confidence: "HIGH",
    security_finding_count: 3,
    finding_counts_by_severity: {
      CRITICAL: 0,
      HIGH: 1,
      MEDIUM: 2,
      LOW: 0,
      INFORMATIONAL: 0,
    },
    highest_severity_finding: "HIGH",
    recommendation_count: 5,
    p1_recommendation_count: 2,
    rag_chunks_used_count: 4,
    analysis_duration_seconds: 180,
    total_files_analyzed: 42,
    total_llm_tokens_used: 15000,
  },
  sections: [
    {
      section_order: 1,
      section_key: "EXECUTIVE_SUMMARY",
      section_title: "Executive Summary",
      content_markdown:
        "This repository implements a **layered architecture** with a FastAPI backend.\n\nOverall health is good.",
    },
    {
      section_order: 2,
      section_key: "SECURITY_FINDINGS",
      section_title: "Security Findings",
      content_markdown:
        "## Findings\n\n| Severity | Count |\n|----------|-------|\n| HIGH | 1 |\n| MEDIUM | 2 |\n\n> **Disclaimer:** These findings are preliminary.",
    },
  ],
};

export const mockReportNullSeverity: ReportResponse = {
  ...mockReport,
  metadata: {
    ...mockReport.metadata,
    security_finding_count: 0,
    finding_counts_by_severity: {
      CRITICAL: 0,
      HIGH: 0,
      MEDIUM: 0,
      LOW: 0,
      INFORMATIONAL: 0,
    },
    highest_severity_finding: null,
  },
};
