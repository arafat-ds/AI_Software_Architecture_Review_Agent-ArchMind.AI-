export type JobStatus = "PENDING" | "RUNNING" | "COMPLETE" | "FAILED";

export type SeverityLevel =
  | "CRITICAL"
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | "INFORMATIONAL";

// POST /jobs request
export interface SubmitJobRequest {
  repo_url: string;
}

// POST /jobs response (202)
export interface SubmitJobResponse {
  job_id: string;
  status: "PENDING";
  message: string;
}

// GET /jobs/{job_id} response
export interface JobStatusResponse {
  job_id: string;
  repo_url: string;
  repo_name: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  report_id: string | null;
  error_message: string | null;
  error_type: string | null;
}

export interface ReportMetadata {
  primary_language: string;
  detected_architecture_pattern: string;
  architecture_confidence: string;
  security_finding_count: number;
  finding_counts_by_severity: Record<SeverityLevel, number>;
  highest_severity_finding: SeverityLevel | null;
  recommendation_count: number;
  p1_recommendation_count: number;
  rag_chunks_used_count: number;
  analysis_duration_seconds: number;
  total_files_analyzed: number;
  total_llm_tokens_used: number;
}

export interface ReportSection {
  section_order: number;
  section_key: string;
  section_title: string;
  content_markdown: string;
}

// GET /reports/{report_id} response
export interface ReportResponse {
  report_id: string;
  job_id: string;
  repo_url: string;
  repo_name: string;
  generated_at: string;
  schema_version: string;
  markdown_content: string;
  metadata: ReportMetadata;
  sections: ReportSection[];
}

// GET /health response
export interface HealthResponse {
  status: string;
  version: string;
  dependencies: {
    gemini: string;
    qdrant: string;
    supabase: string;
  };
}

export type ApiError = {
  detail: string;
};
