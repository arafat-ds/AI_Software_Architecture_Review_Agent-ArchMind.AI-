"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getJob } from "@/lib/api";
import { POLL_INTERVAL_MS, MAX_POLL_DURATION_MS } from "@/lib/constants";
import type { JobStatusResponse } from "@/types/archmind";

interface Props {
  jobId: string;
}

const STATUS_LABELS: Record<string, string> = {
  PENDING: "Queued — waiting to start",
  RUNNING: "Analyzing repository…",
  COMPLETE: "Analysis complete",
  FAILED: "Analysis failed",
};

export default function JobPoller({ jobId }: Props) {
  const router = useRouter();
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startTime = useRef(Date.now());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function clearPoller() {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  useEffect(() => {
    async function poll() {
      if (Date.now() - startTime.current > MAX_POLL_DURATION_MS) {
        setTimedOut(true);
        clearPoller();
        return;
      }

      try {
        const latest = await getJob(jobId);
        setJob(latest);

        if (latest.status === "COMPLETE" && latest.report_id) {
          clearPoller();
          router.push(`/reports/${latest.report_id}`);
          return;
        }

        if (latest.status === "FAILED") {
          clearPoller();
          return;
        }
      } catch (ex) {
        setError(ex instanceof Error ? ex.message : "Poll failed");
        clearPoller();
      }
    }

    poll(); // immediate first poll
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return clearPoller;
  }, [jobId, router]);

  if (timedOut) {
    return (
      <div className="text-center space-y-2">
        <p className="text-yellow-700 font-medium">Analysis timed out after 30 minutes.</p>
        <p className="text-sm text-gray-500">The job may still be running. Check back later.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center">
        <p className="text-red-600" role="alert">
          Error polling job status: {error}
        </p>
      </div>
    );
  }

  if (!job) {
    return <Spinner label="Loading job status…" />;
  }

  const isTerminal = job.status === "COMPLETE" || job.status === "FAILED";

  return (
    <div className="space-y-6 text-center">
      <div className="flex flex-col items-center gap-3">
        {!isTerminal && <Spinner label="" />}
        <p className="text-lg font-semibold text-gray-800">
          {STATUS_LABELS[job.status] ?? job.status}
        </p>
        <p className="text-sm text-gray-500">{job.repo_name}</p>
      </div>

      <div className="text-xs text-gray-400 space-y-1">
        <p>Job ID: {job.job_id}</p>
        {job.started_at && <p>Started: {new Date(job.started_at).toLocaleTimeString()}</p>}
      </div>

      {job.status === "FAILED" && (
        <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700 text-left">
          <p className="font-medium">Analysis failed</p>
          {job.error_message && <p className="mt-1">{job.error_message}</p>}
          {job.error_type && (
            <p className="mt-1 text-xs text-red-500">Error type: {job.error_type}</p>
          )}
        </div>
      )}

      {job.status === "COMPLETE" && (
        <p className="text-green-600 text-sm">Redirecting to report…</p>
      )}
    </div>
  );
}

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 justify-center" role="status" aria-label={label || "Loading"}>
      <svg
        className="animate-spin h-6 w-6 text-indigo-600"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8v8H4z"
        />
      </svg>
      {label && <span className="text-gray-600 text-sm">{label}</span>}
    </div>
  );
}
