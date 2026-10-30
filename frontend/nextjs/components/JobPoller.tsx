"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getJob } from "@/lib/api";
import { POLL_INTERVAL_MS, MAX_POLL_DURATION_MS } from "@/lib/constants";
import type { JobStatusResponse } from "@/types/archmind";

// ─── Stage config ─────────────────────────────────────────────────────────────

interface StageConfig {
  key: string;
  label: string;
  description: string;
}

const STAGES: StageConfig[] = [
  { key: "INGESTING",              label: "Repository Ingestion",  description: "Cloning repository and extracting files"    },
  { key: "PARSING",                label: "Parsing",               description: "Building AST and dependency graph"           },
  { key: "ANALYZING_ARCHITECTURE", label: "Architecture Analysis", description: "Detecting architecture patterns and layers"  },
  { key: "ANALYZING_SECURITY",     label: "Security Analysis",     description: "Scanning for vulnerabilities and misconfigs" },
  { key: "RETRIEVING_RAG",         label: "RAG Retrieval",         description: "Querying architectural knowledge base"       },
  { key: "SYNTHESIZING",           label: "Recommendations",       description: "Generating actionable recommendations"       },
  { key: "ASSEMBLING",             label: "Report Generation",     description: "Compiling final structured report"           },
];

export const STAGE_PERCENT: Record<string, number> = {
  INGESTING: 10,
  PARSING: 25,
  ANALYZING_ARCHITECTURE: 40,
  ANALYZING_SECURITY: 55,
  RETRIEVING_RAG: 65,
  SYNTHESIZING: 75,
  ASSEMBLING: 85,
  PERSISTING: 95,
};

export const SMOOTH_TICK_MS = 500;

type StepState = "pending" | "active" | "complete" | "failed";

function getStepStates(currentStage: string | null, jobStatus: string): StepState[] {
  if (jobStatus === "COMPLETE") return STAGES.map(() => "complete");
  if (currentStage === "PERSISTING") return STAGES.map(() => "complete");
  const activeIdx = currentStage ? STAGES.findIndex((s) => s.key === currentStage) : -1;
  return STAGES.map((_, i) => {
    if (activeIdx === -1) return "pending";
    if (i < activeIdx) return "complete";
    if (i === activeIdx) return jobStatus === "FAILED" ? "failed" : "active";
    return "pending";
  });
}

function getTargetPercent(currentStage: string | null, jobStatus: string): number {
  if (jobStatus === "COMPLETE") return 100;
  if (!currentStage) return 0;
  return STAGE_PERCENT[currentStage] ?? 0;
}

function getActiveStageLabel(currentStage: string | null, jobStatus: string): string {
  if (jobStatus === "COMPLETE") return "Complete";
  if (jobStatus === "PENDING") return "Queued";
  if (currentStage === "PERSISTING") return "Saving Report";
  const stage = STAGES.find((s) => s.key === currentStage);
  return stage?.label ?? "Initializing";
}

// ─── Diamond DAG graph ────────────────────────────────────────────────────────
//
//  GitHub → Parser ──→ Arch Analyzer ──→ RAG KB      ──→ Report
//                  ↘→ Sec Analyzer  ──→ Rec Engine  ──↗

const VIZ_NODES = [
  { id: 0, cx: 80,  cy: 240, abbr: "GH",    label: "GitHub",       sublabel: "Repository" },
  { id: 1, cx: 230, cy: 240, abbr: "PARSE", label: "Source",       sublabel: "Parser"     },
  { id: 2, cx: 415, cy: 125, abbr: "ARCH",  label: "Architecture", sublabel: "Analyzer"   },
  { id: 3, cx: 415, cy: 355, abbr: "SEC",   label: "Security",     sublabel: "Analyzer"   },
  { id: 4, cx: 595, cy: 125, abbr: "RAG",   label: "RAG",          sublabel: "Knowledge"  },
  { id: 5, cx: 595, cy: 355, abbr: "REC",   label: "Rec.",         sublabel: "Engine"     },
  { id: 6, cx: 760, cy: 240, abbr: "RPT",   label: "Report",       sublabel: "Generator"  },
];

const VIZ_EDGES = [
  { from: 0, to: 1 },
  { from: 1, to: 2 },
  { from: 1, to: 3 },
  { from: 2, to: 4 },
  { from: 3, to: 5 },
  { from: 4, to: 6 },
  { from: 5, to: 6 },
];

const R = 30;

function edgePts(a: (typeof VIZ_NODES)[0], b: (typeof VIZ_NODES)[0]) {
  const dx = b.cx - a.cx, dy = b.cy - a.cy;
  const len = Math.sqrt(dx * dx + dy * dy);
  const ux = dx / len, uy = dy / len;
  return {
    x1: a.cx + (R + 3) * ux, y1: a.cy + (R + 3) * uy,
    x2: b.cx - (R + 9) * ux, y2: b.cy - (R + 9) * uy,
  };
}

function ArchGraph({ stepStates }: { stepStates: StepState[] }) {
  return (
    <svg viewBox="0 0 860 480" className="w-full h-full" aria-hidden="true" style={{ maxHeight: "100%" }}>
      <defs>
        <marker id="mk-a" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
          <path d="M0,0.5 L0,6.5 L6.5,3.5 z" fill="#22d3ee" />
        </marker>
        <marker id="mk-c" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
          <path d="M0,0.5 L0,6.5 L6.5,3.5 z" fill="#10b981" />
        </marker>
        <marker id="mk-p" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
          <path d="M0,0.5 L0,6.5 L6.5,3.5 z" fill="#1e3a5f" />
        </marker>
        <filter id="ga" x="-60%" y="-60%" width="220%" height="220%">
          <feGaussianBlur stdDeviation="7" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="gc" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {VIZ_EDGES.map(({ from, to }) => {
        const toState = stepStates[to] ?? "pending";
        const active   = toState === "active";
        const complete = toState === "complete";
        const { x1, y1, x2, y2 } = edgePts(VIZ_NODES[from], VIZ_NODES[to]);
        return (
          <g key={`e${from}-${to}`}>
            <line
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={complete ? "#10b981" : active ? "#22d3ee" : "#1e3a5f"}
              strokeOpacity={complete || active ? 0.8 : 0.22}
              strokeWidth={active ? 2 : 1.5}
              markerEnd={complete ? "url(#mk-c)" : active ? "url(#mk-a)" : "url(#mk-p)"}
            />
            {active && (
              <circle r="3.5" fill="#67e8f9" opacity="0.9" className="motion-reduce:hidden">
                <animateMotion dur="1.4s" repeatCount="indefinite"
                  path={`M ${x1} ${y1} L ${x2} ${y2}`} />
              </circle>
            )}
          </g>
        );
      })}

      {VIZ_NODES.map((n, i) => {
        const st   = stepStates[i] ?? "pending";
        const isA  = st === "active";
        const isC  = st === "complete";
        const isF  = st === "failed";
        const fill = isF ? "#3b0f0f" : isC ? "#041f11" : isA ? "#091a33" : "#0a1628";
        const strk = isF ? "#ef4444" : isC ? "#10b981" : isA ? "#22d3ee" : "#1e3a5f";
        const tCol = isF ? "#fca5a5" : isC ? "#6ee7b7" : isA ? "#67e8f9" : "#2a3a52";
        return (
          <g key={n.id}>
            {isA && (
              <circle cx={n.cx} cy={n.cy} r={R + 16}
                fill="none" stroke="#22d3ee" strokeWidth="1" opacity="0.18"
                style={{ transformBox: "fill-box", transformOrigin: "center" }}
                className="animate-pulse motion-reduce:animate-none"
              />
            )}
            <circle cx={n.cx} cy={n.cy} r={R}
              fill={fill} stroke={strk} strokeWidth={isA ? 2 : 1.5}
              filter={isA ? "url(#ga)" : isC ? "url(#gc)" : undefined}
            />
            {isC
              ? <text x={n.cx} y={n.cy + 5} textAnchor="middle" fontSize="15" fill="#10b981" fontWeight="700">✓</text>
              : isF
              ? <text x={n.cx} y={n.cy + 5} textAnchor="middle" fontSize="15" fill="#ef4444" fontWeight="700">✕</text>
              : <text x={n.cx} y={n.cy + 4} textAnchor="middle" fontSize="9" fill={tCol}
                  fontWeight={isA ? "700" : "500"} fontFamily="monospace">{n.abbr}</text>
            }
            <text x={n.cx} y={n.cy + R + 15} textAnchor="middle" fontSize="8.5" fill={tCol} fontFamily="monospace">{n.label}</text>
            <text x={n.cx} y={n.cy + R + 27} textAnchor="middle" fontSize="8.5" fill={tCol} fontFamily="monospace">{n.sublabel}</text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  if (status === "FAILED")
    return <span className="text-xs font-bold tracking-widest text-red-400 border border-red-500/40 rounded px-3 py-1.5">FAILED</span>;
  if (status === "COMPLETE")
    return <span className="text-xs font-bold tracking-widest text-emerald-400 border border-emerald-500/40 rounded px-3 py-1.5">COMPLETE</span>;
  if (status === "PENDING")
    return <span className="text-xs font-bold tracking-widest text-slate-400 border border-slate-600/40 rounded px-3 py-1.5">QUEUED</span>;
  return (
    <span className="flex items-center gap-1.5 text-xs font-bold tracking-widest text-cyan-400 border border-cyan-500/40 rounded px-3 py-1.5">
      <svg className="animate-spin h-3 w-3 motion-reduce:animate-none" fill="none" viewBox="0 0 24 24" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      ANALYZING
    </span>
  );
}

// ─── Agent workflow panel ─────────────────────────────────────────────────────

function AgentWorkflow({
  stepStates,
  stageSeenAt,
  now,
}: {
  stepStates: StepState[];
  stageSeenAt: Record<string, number>;
  now: number;
}) {
  return (
    <div className="relative flex flex-col">
      <div className="absolute left-[9px] top-3 bottom-3 w-px bg-slate-800/80" />
      {STAGES.map((stage, i) => {
        const state  = stepStates[i];
        const seenAt = stageSeenAt[stage.key];
        let timing = "Pending —";
        if (state === "complete") {
          timing = "Completed";
        } else if (state === "active") {
          const elapsed = seenAt ? Math.floor((now - seenAt) / 1000) : 0;
          timing = `In progress ${elapsed}s`;
        } else if (state === "failed") {
          timing = "Failed";
        }
        return (
          <div key={stage.key} className="relative flex gap-3 pb-5 last:pb-0">
            <div className="relative z-10 flex-shrink-0 mt-0.5">
              {state === "complete" && (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/15 border border-emerald-500/50 text-emerald-400 text-xs font-bold">✓</span>
              )}
              {state === "active" && (
                <span className="flex h-5 w-5 items-center justify-center rounded-full border border-cyan-400/70 bg-[#060e1c]">
                  <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 animate-pulse motion-reduce:animate-none" />
                </span>
              )}
              {state === "failed" && (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500/15 border border-red-500/50 text-red-400 text-xs font-bold">✕</span>
              )}
              {state === "pending" && (
                <span className="flex h-5 w-5 items-center justify-center rounded-full border border-slate-700/50 bg-[#060e1c]" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className={[
                  "text-sm font-medium leading-tight",
                  state === "active"   ? "text-cyan-300"    : "",
                  state === "failed"   ? "text-red-400"     : "",
                  state === "complete" ? "text-emerald-400" : "",
                  state === "pending"  ? "text-slate-600"   : "",
                ].join(" ")}>{stage.label}</span>
                <span className={[
                  "text-xs flex-shrink-0 font-mono",
                  state === "active"   ? "text-cyan-600"    : "",
                  state === "complete" ? "text-emerald-800" : "",
                  state === "failed"   ? "text-red-700"     : "",
                  state === "pending"  ? "text-slate-700"   : "",
                ].join(" ")}>{timing}</span>
              </div>
              <p className={[
                "text-xs mt-0.5 leading-snug",
                state === "active" ? "text-slate-400" : "text-slate-600",
              ].join(" ")}>{stage.description}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Error panel ──────────────────────────────────────────────────────────────

function ErrorPanel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-red-800/50 bg-red-950/25 p-4 text-sm">
      <p className="font-semibold text-red-400 mb-1">{title}</p>
      <div className="text-red-500 space-y-1">{children}</div>
      <a href="/" className="mt-3 inline-block text-cyan-400 underline underline-offset-2 text-xs hover:text-cyan-300">
        ← Return to Home
      </a>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function JobPoller({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [job, setJob]               = useState<JobStatusResponse | null>(null);
  const [pollError, setPollError]   = useState<string | null>(null);
  const [timedOut, setTimedOut]     = useState(false);
  const [smoothPercent, setSmoothPercent] = useState(0);
  const [now, setNow]               = useState(Date.now());

  const startTime   = useRef(Date.now());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobRef      = useRef<JobStatusResponse | null>(null);
  const stageSeenAt = useRef<Record<string, number>>({});
  // Use a ref so router never triggers polling effect re-runs (test mock returns new object each render)
  const routerRef   = useRef(router);
  routerRef.current = router;

  useEffect(() => {
    jobRef.current = job;
    if (job?.status === "COMPLETE") setSmoothPercent(100);
    if (job?.current_stage && !stageSeenAt.current[job.current_stage]) {
      stageSeenAt.current[job.current_stage] = Date.now();
    }
  }, [job]);

  // Polling
  useEffect(() => {
    function clearPoller() {
      if (intervalRef.current !== null) { clearInterval(intervalRef.current); intervalRef.current = null; }
    }
    async function poll() {
      if (Date.now() - startTime.current > MAX_POLL_DURATION_MS) { setTimedOut(true); clearPoller(); return; }
      try {
        const latest = await getJob(jobId);
        setJob(latest);
        if (latest.status === "COMPLETE" && latest.report_id) { clearPoller(); routerRef.current.push(`/reports/${latest.report_id}`); return; }
        if (latest.status === "FAILED") { clearPoller(); return; }
      } catch (ex) {
        setPollError(ex instanceof Error ? ex.message : "Poll failed");
        clearPoller();
      }
    }
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return clearPoller;
  }, [jobId]);

  // Smooth estimated progress — increments 1%/tick, never backward
  useEffect(() => {
    const id = setInterval(() => {
      const j = jobRef.current;
      if (!j) return;
      const target = getTargetPercent(j.current_stage, j.status);
      setSmoothPercent((prev) => (prev >= target ? prev : prev + 1));
    }, SMOOTH_TICK_MS);
    return () => clearInterval(id);
  }, []);

  // Elapsed timer for active stage display
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // ── Terminal: timeout ────────────────────────────────────────────────────────
  if (timedOut) {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#060a14]">
        <div className="rounded-xl border border-amber-700/40 bg-[#0d1b35] p-8 max-w-md space-y-3">
          <p className="font-semibold text-amber-400 tracking-wide text-sm">
            Analysis timed out in this browser tab
          </p>
          <p className="text-slate-400 text-sm leading-relaxed">
            The backend job may still be running — check back later using the same URL.
            Closing this tab does not cancel the analysis.
          </p>
          <a href="/" className="inline-block text-cyan-400 underline underline-offset-2 text-xs hover:text-cyan-300">
            ← Return to Home
          </a>
        </div>
      </div>
    );
  }

  // ── Terminal: network error ──────────────────────────────────────────────────
  if (pollError) {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#060a14]">
        <ErrorPanel title="Error polling job status">
          <p>{pollError}</p>
        </ErrorPanel>
      </div>
    );
  }

  // ── Loading skeleton ─────────────────────────────────────────────────────────
  if (!job) {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#060a14]" role="status">
        <div className="flex items-center gap-3 text-slate-400 text-sm">
          <svg className="animate-spin h-5 w-5 text-cyan-500 motion-reduce:animate-none" fill="none" viewBox="0 0 24 24" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Loading job status…
        </div>
      </div>
    );
  }

  const { status, current_stage, repo_name, job_id, started_at, error_message, error_type } = job;
  const stepStates       = getStepStates(current_stage, status);
  const activeStageLabel = getActiveStageLabel(current_stage, status);
  const isIndeterminate  = status === "RUNNING" && !current_stage && smoothPercent === 0;

  const formattedStart = started_at
    ? new Date(started_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" })
    : null;

  return (
    <div className="fixed inset-0 z-[100] flex flex-col bg-[#060a14] overflow-hidden">

      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <header className="flex-shrink-0 flex items-center gap-4 px-6 h-14 bg-[#060e1c] border-b border-slate-800/60">
        {/* Hex logo */}
        <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
          <polygon points="14,2 24,7.5 24,20.5 14,26 4,20.5 4,7.5"
            fill="none" stroke="#22d3ee" strokeWidth="1.5" />
          <circle cx="14" cy="9"  r="2.2" fill="#22d3ee" opacity="0.85" />
          <circle cx="8"  cy="20" r="2.2" fill="#22d3ee" opacity="0.5"  />
          <circle cx="20" cy="20" r="2.2" fill="#22d3ee" opacity="0.5"  />
          <line x1="14" y1="11.2" x2="8"  y2="17.8" stroke="#22d3ee" strokeWidth="1" opacity="0.35" />
          <line x1="14" y1="11.2" x2="20" y2="17.8" stroke="#22d3ee" strokeWidth="1" opacity="0.35" />
        </svg>

        <div className="leading-tight">
          <div className="text-sm font-extrabold tracking-[0.2em] text-slate-100">ARCHMIND AI</div>
          <div className="text-xs tracking-[0.12em] text-slate-500">ARCHITECTURE ANALYSIS LAB</div>
        </div>

        <div className="w-px h-7 bg-slate-700/60 mx-1" />

        {/* GitHub + repo */}
        <div className="flex items-center gap-2">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="#64748b" aria-hidden="true">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.2 11.38.6.1.82-.26.82-.58v-2.02c-3.34.72-4.04-1.6-4.04-1.6-.54-1.38-1.34-1.74-1.34-1.74-1.08-.74.08-.72.08-.72 1.2.08 1.84 1.24 1.84 1.24 1.06 1.82 2.78 1.3 3.46 1 .1-.78.42-1.3.76-1.6-2.66-.3-5.46-1.34-5.46-5.94 0-1.3.46-2.38 1.22-3.22-.12-.3-.54-1.52.12-3.18 0 0 1-.32 3.3 1.22a11.5 11.5 0 013-.4c1.02.004 2.04.14 3 .4 2.28-1.54 3.28-1.22 3.28-1.22.66 1.66.24 2.88.12 3.18.76.84 1.22 1.92 1.22 3.22 0 4.6-2.8 5.62-5.48 5.92.44.38.82 1.12.82 2.24v3.32c0 .32.22.7.84.58C20.58 21.8 24 17.3 24 12c0-6.63-5.37-12-12-12z" />
          </svg>
          <span className="text-xs text-slate-600 font-mono">Repository</span>
          {repo_name && <span className="text-xs text-slate-300 font-mono font-semibold">{repo_name}</span>}
        </div>

        <div className="ml-auto">
          <StatusBadge status={status} />
        </div>
      </header>

      {/* ── Main area ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Left: architecture graph */}
        <div className="flex-[3] border-r border-slate-800/60 flex flex-col p-5 min-w-0 overflow-hidden">
          <p className="text-xs font-bold tracking-[0.16em] text-slate-600 mb-3 flex-shrink-0">
            LIVE ARCHITECTURE GRAPH
          </p>
          <div className="flex-1 flex items-center justify-center min-h-0">
            <ArchGraph stepStates={stepStates} />
          </div>
          {status === "FAILED" && (
            <div className="flex-shrink-0 mt-4">
              <ErrorPanel title="Analysis failed">
                {error_message && <p>{error_message}</p>}
                {error_type && (
                  <p className="text-xs text-red-600 font-mono">Error type: {error_type}</p>
                )}
              </ErrorPanel>
            </div>
          )}
        </div>

        {/* Right: agent workflow */}
        <div className="flex-[2] flex flex-col p-5 overflow-y-auto min-w-0">
          <p className="text-xs font-bold tracking-[0.16em] text-slate-600 mb-5 flex-shrink-0">
            AGENT WORKFLOW
          </p>
          <AgentWorkflow
            stepStates={stepStates}
            stageSeenAt={stageSeenAt.current}
            now={now}
          />
        </div>
      </div>

      {/* ── Progress section ───────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-slate-800/60 bg-[#060e1c] px-6 py-4">
        <div className="flex items-center gap-4 mb-3">
          {/* Bar chart icon */}
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <rect x="1"  y="9"  width="3" height="6"  rx="0.8" fill="#334155" />
            <rect x="6"  y="5"  width="3" height="10" rx="0.8" fill="#475569" />
            <rect x="11" y="1"  width="3" height="14" rx="0.8" fill="#22d3ee" opacity="0.65" />
          </svg>
          <span className="text-xs font-bold tracking-[0.18em] text-slate-500">ESTIMATED PROGRESS</span>

          <div className="w-px h-6 bg-slate-700/50" />

          <span className="text-3xl font-extrabold text-cyan-400 tabular-nums leading-none">
            {isIndeterminate ? "—" : `${smoothPercent}%`}
          </span>

          <div className="w-px h-6 bg-slate-700/50" />

          <p className="flex-1 text-xs text-slate-500 min-w-0 leading-snug">
            {isIndeterminate
              ? "Initializing analysis pipeline…"
              : status === "COMPLETE"
              ? "Analysis complete — redirecting to report."
              : status === "FAILED"
              ? "Analysis stopped due to an error."
              : "Repository analysis is in progress. Stage-based estimate — not a measured completion percentage."}
          </p>

          <span className="text-xs text-slate-500 font-mono flex-shrink-0">{activeStageLabel}</span>
        </div>

        <div className="h-1.5 w-full rounded-full bg-[#0a1628] overflow-hidden">
          {isIndeterminate ? (
            <div className="h-full w-1/4 rounded-full bg-cyan-800/60 animate-pulse motion-reduce:animate-none" />
          ) : (
            <div
              className="h-full rounded-full bg-cyan-500 transition-all duration-300"
              style={{ width: `${smoothPercent}%` }}
              role="progressbar"
              aria-valuenow={smoothPercent}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          )}
        </div>
      </div>

      {/* ── Footer ────────────────────────────────────────────────────────────── */}
      <footer className="flex-shrink-0 border-t border-slate-800/80 bg-[#040810] px-6 py-2 flex items-center gap-6">
        {formattedStart && (
          <div className="flex items-center gap-1.5 text-xs text-slate-700 font-mono">
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden="true">
              <circle cx="5.5" cy="5.5" r="4.5" stroke="#334155" strokeWidth="1.1" />
              <line x1="5.5" y1="2.5" x2="5.5" y2="6" stroke="#334155" strokeWidth="1.1" strokeLinecap="round" />
              <line x1="5.5" y1="6" x2="7.5" y2="7" stroke="#334155" strokeWidth="1.1" strokeLinecap="round" />
            </svg>
            Started: {formattedStart}
          </div>
        )}
        <div className="flex items-center gap-1.5 text-xs text-slate-700 font-mono">
          <svg width="10" height="12" viewBox="0 0 10 12" fill="none" aria-hidden="true">
            <rect x="0.6" y="0.6" width="8.8" height="10.8" rx="1.4" stroke="#334155" strokeWidth="1.1" />
            <line x1="2.5" y1="4" x2="7.5" y2="4" stroke="#334155" strokeWidth="0.9" />
            <line x1="2.5" y1="6" x2="7.5" y2="6" stroke="#334155" strokeWidth="0.9" />
            <line x1="2.5" y1="8" x2="5.5" y2="8" stroke="#334155" strokeWidth="0.9" />
          </svg>
          Job ID: {job_id}
        </div>
      </footer>
    </div>
  );
}
