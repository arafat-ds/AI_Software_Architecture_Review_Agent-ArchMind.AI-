/**
 * Client-side API module — calls Next.js Route Handlers only.
 * The browser never sees ARCHMIND_API_KEY; the Route Handlers inject it server-side.
 */

import type {
  SubmitJobRequest,
  SubmitJobResponse,
  JobStatusResponse,
  ReportResponse,
  HealthResponse,
} from "@/types/archmind";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function submitJob(req: SubmitJobRequest): Promise<SubmitJobResponse> {
  return apiFetch<SubmitJobResponse>("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function getJob(jobId: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/api/jobs/${jobId}`);
}

export async function getReport(reportId: string): Promise<ReportResponse> {
  return apiFetch<ReportResponse>(`/api/reports/${reportId}`);
}

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}
