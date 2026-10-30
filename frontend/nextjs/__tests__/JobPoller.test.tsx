import { render, screen, act, waitFor } from "@testing-library/react";
import JobPoller from "@/components/JobPoller";
import * as api from "@/lib/api";
import type { JobStatusResponse } from "@/types/archmind";

// Mock Next.js router
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// Mock API
jest.mock("@/lib/api", () => ({
  getJob: jest.fn(),
}));

const mockGetJob = api.getJob as jest.MockedFunction<typeof api.getJob>;

beforeEach(() => {
  jest.useFakeTimers();
  mockPush.mockClear();
  mockGetJob.mockClear();
});

afterEach(() => {
  jest.useRealTimers();
});

function makeJob(overrides: Partial<JobStatusResponse> = {}): JobStatusResponse {
  return {
    job_id: "job-abc-123",
    repo_url: "https://github.com/owner/repo",
    repo_name: "repo",
    status: "RUNNING",
    created_at: "2024-01-01T00:00:00Z",
    started_at: "2024-01-01T00:00:01Z",
    completed_at: null,
    report_id: null,
    error_message: null,
    error_type: null,
    current_stage: null,
    ...overrides,
  };
}

// Helper: let the initial poll resolve without advancing the fake clock.
// The immediate poll() call in useEffect is async; wrapping in act flushes
// the Promise microtask queue so React state updates are applied.
async function flushInitialPoll() {
  await act(async () => {
    await Promise.resolve();
  });
}

// Advance fake timers by ms and flush all resulting React state updates.
async function advanceAndFlush(ms: number) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
    await Promise.resolve();
  });
}

// ---------------------------------------------------------------------------
// 1. PENDING status
// ---------------------------------------------------------------------------

test("shows queued label when status is PENDING", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "PENDING", current_stage: null }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  // "Queued" appears in status badge ("QUEUED") and active stage label ("Queued")
  expect(screen.getAllByText(/Queued/i).length).toBeGreaterThanOrEqual(1);
});

// ---------------------------------------------------------------------------
// 2. RUNNING with no current_stage — indeterminate
// ---------------------------------------------------------------------------

test("shows indeterminate state when RUNNING with no stage", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: null }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  // "Initializing" appears in both the active label and the description paragraph
  expect(screen.getAllByText(/Initializing/i).length).toBeGreaterThanOrEqual(1);
  // No percentage value in indeterminate mode
  expect(screen.queryByText(/^\d+%$/)).not.toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 3. RUNNING with current_stage INGESTING — stage 1 active
// ---------------------------------------------------------------------------

test("shows stage 1 active when current_stage is INGESTING", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: "INGESTING" }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  // Label appears in both the stage list and the active stage label in the progress section
  expect(screen.getAllByText("Repository Ingestion").length).toBeGreaterThanOrEqual(1);
  // Advance smooth animation to reach INGESTING ceiling (10%): 10 ticks × 500ms
  await advanceAndFlush(10 * 500);
  expect(screen.getByText("10%")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 4. RUNNING with current_stage PARSING — stage 2 active
// ---------------------------------------------------------------------------

test("shows stage 2 active when current_stage is PARSING", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: "PARSING" }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  expect(screen.getAllByText("Parsing").length).toBeGreaterThanOrEqual(1);
  // 25 ticks × 500ms to reach PARSING ceiling (25%)
  await advanceAndFlush(25 * 500);
  expect(screen.getByText("25%")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 5. RUNNING with current_stage ANALYZING_ARCHITECTURE — stage 3 active
// ---------------------------------------------------------------------------

test("shows stage 3 active when current_stage is ANALYZING_ARCHITECTURE", async () => {
  mockGetJob.mockResolvedValue(
    makeJob({ status: "RUNNING", current_stage: "ANALYZING_ARCHITECTURE" })
  );
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  expect(screen.getAllByText("Architecture Analysis").length).toBeGreaterThanOrEqual(1);
  // 40 ticks × 500ms to reach ANALYZING_ARCHITECTURE ceiling (40%)
  await advanceAndFlush(40 * 500);
  expect(screen.getByText("40%")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 6. RUNNING with current_stage PERSISTING — all 7 visible steps complete
// ---------------------------------------------------------------------------

test("shows 95% and saving label when current_stage is PERSISTING", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: "PERSISTING" }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  // 95 ticks × 500ms to reach PERSISTING ceiling (95%)
  await advanceAndFlush(95 * 500);
  expect(screen.getByText("95%")).toBeInTheDocument();
  expect(screen.getAllByText(/Saving report/i).length).toBeGreaterThanOrEqual(1);
});

// ---------------------------------------------------------------------------
// 7. COMPLETE — redirect to report
// ---------------------------------------------------------------------------

test("redirects to report when status is COMPLETE", async () => {
  mockGetJob.mockResolvedValue(
    makeJob({
      status: "COMPLETE",
      report_id: "report-xyz",
      completed_at: "2024-01-01T00:05:00Z",
    })
  );
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  expect(mockPush).toHaveBeenCalledWith("/reports/report-xyz");
});

// ---------------------------------------------------------------------------
// 8. FAILED with a known stage
// ---------------------------------------------------------------------------

test("shows failed state when status is FAILED with a known stage", async () => {
  mockGetJob.mockResolvedValue(
    makeJob({
      status: "FAILED",
      current_stage: "ANALYZING_SECURITY",
      error_message: "LLM token limit exceeded",
      error_type: "SecurityAnalysisNode.FatalNodeError",
    })
  );
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  expect(screen.getByText(/Analysis failed/i)).toBeInTheDocument();
  expect(screen.getByText("LLM token limit exceeded")).toBeInTheDocument();
  expect(screen.getByText(/SecurityAnalysisNode/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Return to Home/i })).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 9. FAILED with no current_stage
// ---------------------------------------------------------------------------

test("shows error message when FAILED with no stage info", async () => {
  mockGetJob.mockResolvedValue(
    makeJob({
      status: "FAILED",
      current_stage: null,
      error_message: "Repository clone failed",
      error_type: "CloneTimeoutError",
    })
  );
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  expect(screen.getByText("Repository clone failed")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 10. Poll network error — stops polling, shows message
// ---------------------------------------------------------------------------

test("shows error and stops polling on network failure", async () => {
  mockGetJob.mockRejectedValue(new Error("Network request failed"));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  expect(screen.getByText(/Error polling job status/i)).toBeInTheDocument();
  expect(screen.getByText("Network request failed")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Return to Home/i })).toBeInTheDocument();

  // Polling must have stopped — advancing 20s should produce no new getJob calls
  const callCount = mockGetJob.mock.calls.length;
  await act(async () => {
    jest.advanceTimersByTime(20_000);
  });
  expect(mockGetJob.mock.calls.length).toBe(callCount);
});

// ---------------------------------------------------------------------------
// 11. Timeout — shows browser-timeout message, not job cancellation
// ---------------------------------------------------------------------------

test("shows browser timeout message after MAX_POLL_DURATION_MS", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: "INGESTING" }));
  render(<JobPoller jobId="job-abc-123" />);

  // Advance past the 30-minute timeout (MAX_POLL_DURATION_MS = 1_800_000)
  await act(async () => {
    jest.advanceTimersByTime(31 * 60 * 1000);
    await Promise.resolve();
  });

  expect(screen.getByText(/timed out in this browser tab/i)).toBeInTheDocument();
  expect(screen.getByText(/backend job may still be running/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Return to Home/i })).toBeInTheDocument();
  expect(mockPush).not.toHaveBeenCalled();
});

// ---------------------------------------------------------------------------
// 12. Estimate disclaimer visible when stage percentage is shown
// ---------------------------------------------------------------------------

test("shows estimate disclaimer when a real stage percentage is displayed", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: "PARSING" }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  expect(screen.getByText(/Stage-based estimate/i)).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 13. Smooth progress: percentage never decreases across poll cycles
// ---------------------------------------------------------------------------

test("smooth percentage never decreases when stage stays the same", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: "PARSING" }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  // Advance partway toward PARSING ceiling (25%) — reach ~12%
  await advanceAndFlush(12 * 500);
  const pctBefore = parseInt(screen.getByText(/^\d+%$/).textContent ?? "");
  expect(pctBefore).toBeGreaterThan(0);

  // Another advance — value must not decrease
  await advanceAndFlush(5 * 500);
  const pctAfter = parseInt(screen.getByText(/^\d+%$/).textContent ?? "");
  expect(pctAfter).toBeGreaterThanOrEqual(pctBefore);
});

// ---------------------------------------------------------------------------
// 14. Smooth progress: percentage does not overshoot stage ceiling
// ---------------------------------------------------------------------------

test("percentage stops at stage ceiling and does not overshoot", async () => {
  mockGetJob.mockResolvedValue(makeJob({ status: "RUNNING", current_stage: "INGESTING" }));
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  // Advance well beyond INGESTING ceiling (10%): 30 ticks
  await advanceAndFlush(30 * 500);
  expect(screen.getByText("10%")).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// 15. Smooth progress: 100% only on COMPLETE
// ---------------------------------------------------------------------------

test("percentage reaches 100% only when status is COMPLETE", async () => {
  const runningJob = makeJob({ status: "RUNNING", current_stage: "ASSEMBLING" });
  const completeJob = makeJob({
    status: "COMPLETE",
    report_id: "r-1",
    completed_at: "2024-01-01T01:00:00Z",
  });

  // Use infinite RUNNING responses during animation; switch to COMPLETE afterwards.
  // This avoids counting exact poll invocations (which vary due to effect re-runs).
  mockGetJob.mockResolvedValue(runningJob);
  render(<JobPoller jobId="job-abc-123" />);
  await flushInitialPoll();

  // Advance well past ASSEMBLING ceiling (85 ticks needed, 200 ticks used for safety)
  await advanceAndFlush(200 * 500);
  // smoothPercent should be capped at 85, never 100%
  expect(screen.getByText("85%")).toBeInTheDocument();

  // Now switch mock to COMPLETE and trigger a poll
  mockGetJob.mockResolvedValue(completeJob);
  await advanceAndFlush(10_000);
  expect(mockPush).toHaveBeenCalledWith("/reports/r-1");
});
