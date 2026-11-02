"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { ReportResponse, SeverityLevel } from "@/types/archmind";
import MarkdownContent from "./report/MarkdownContent";
import DonutChart from "./report/DonutChart";

// ── Navigation ────────────────────────────────────────────────────────────────

const NAV_SECTIONS = [
  { id: "hero",              label: "Overview",          num: "01" },
  { id: "kpi",               label: "Key Metrics",       num: "02" },
  { id: "executive-summary", label: "Executive Summary", num: "03" },
  { id: "architecture",      label: "Architecture",      num: "04" },
  { id: "security",          label: "Security",          num: "05" },
  { id: "pipeline",          label: "Analysis Pipeline", num: "06" },
  { id: "repository",        label: "Repository",        num: "07" },
  { id: "recommendations",   label: "Recommendations",   num: "08" },
  { id: "next-steps",        label: "Next Steps",        num: "09" },
  { id: "export",            label: "Export",            num: "10" },
] as const;

type SectionId = (typeof NAV_SECTIONS)[number]["id"];

// ── Styling constants ─────────────────────────────────────────────────────────

const SEV_STYLES: Record<
  SeverityLevel,
  { dot: string; text: string; bg: string; border: string }
> = {
  CRITICAL:      { dot: "#f85149", text: "text-[#f85149]", bg: "bg-[#2d1b1b]",  border: "border-[#5c2626]" },
  HIGH:          { dot: "#db6d28", text: "text-[#db6d28]", bg: "bg-[#2d1e0f]",  border: "border-[#5c3a1a]" },
  MEDIUM:        { dot: "#d29922", text: "text-[#d29922]", bg: "bg-[#2d2109]",  border: "border-[#5c4110]" },
  LOW:           { dot: "#58a6ff", text: "text-[#58a6ff]", bg: "bg-[#0c1929]",  border: "border-[#1a3060]" },
  INFORMATIONAL: { dot: "#6e7681", text: "text-[#6e7681]", bg: "bg-[#1c2128]",  border: "border-[#30363d]" },
};

const CONF_STYLES: Record<string, { bar: string; width: string; text: string }> = {
  HIGH:   { bar: "bg-[#3fb950]", width: "w-full",  text: "text-[#3fb950]" },
  MEDIUM: { bar: "bg-[#d29922]", width: "w-2/3",   text: "text-[#d29922]" },
  LOW:    { bar: "bg-[#f85149]", width: "w-1/3",   text: "text-[#f85149]" },
};

type Accent = "blue" | "green" | "yellow" | "red" | "orange";
const ACCENT: Record<Accent, { val: string; sub: string }> = {
  blue:   { val: "text-[#58a6ff]", sub: "text-[#388bfd]" },
  green:  { val: "text-[#3fb950]", sub: "text-[#26a641]" },
  yellow: { val: "text-[#d29922]", sub: "text-[#9e6a03]" },
  red:    { val: "text-[#f85149]", sub: "text-[#da3633]" },
  orange: { val: "text-[#db6d28]", sub: "text-[#bd561d]" },
};

const SEVERITY_ORDER: SeverityLevel[] = [
  "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL",
];

const PIPELINE_STAGES = [
  "Repository Ingestion",
  "Code Parsing & AST Analysis",
  "Architecture Analysis",
  "Security Vulnerability Scan",
  "Code Quality Assessment",
  "Recommendations Generation",
  "Report Compilation",
];

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  report: ReportResponse;
}

export default function ReportViewer({ report }: Props) {
  const { metadata, sections } = report;
  const [active, setActive] = useState<SectionId>("hero");

  const sectionMap = Object.fromEntries(
    sections.map(s => [s.section_key, s.content_markdown])
  );

  // Scroll-spy: track which section is at top of viewport
  useEffect(() => {
    const ids = NAV_SECTIONS.map(s => s.id);
    function onScroll() {
      const threshold = 100;
      let current: SectionId = "hero";
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= threshold) {
          current = id as SectionId;
        }
      }
      setActive(current);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const confidence = (metadata.architecture_confidence ?? "").toUpperCase();
  const confStyle = CONF_STYLES[confidence] ?? CONF_STYLES.LOW;
  const totalFindings = metadata.security_finding_count;

  return (
    <div className="flex flex-1 bg-[#0d1117]">

      {/* ── Left sidebar ─────────────────────────────────────────────────── */}
      <aside
        className="hidden lg:flex flex-col w-56 flex-shrink-0 border-r border-[#21262d] bg-[#0d1117] self-start sticky top-14 overflow-y-auto"
        style={{ height: "calc(100vh - 56px)" }}
      >
        {/* Branding */}
        <div className="px-4 py-4 border-b border-[#21262d]">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-gradient-to-br from-[#22d3ee] to-[#7c3aed] flex-shrink-0" />
            <span className="text-xs font-semibold text-[#e6edf3] tracking-wide">
              Analysis Report
            </span>
          </div>
          <p className="mt-1 text-[10px] text-[#6e7681] truncate" title={report.repo_name}>
            {report.repo_name}
          </p>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-2 px-2" aria-label="Report sections">
          {NAV_SECTIONS.map(({ id, label, num }) => {
            const isActive = active === id;
            return (
              <button
                key={id}
                onClick={() => scrollTo(id)}
                className={[
                  "w-full text-left px-3 py-2 rounded-md flex items-center gap-2.5 transition-colors duration-150 mb-0.5",
                  isActive
                    ? "bg-[#1f6feb]/20 text-[#58a6ff]"
                    : "text-[#6e7681] hover:text-[#cdd9e5] hover:bg-[#1c2128]",
                ].join(" ")}
              >
                <span
                  className={`text-[10px] font-mono tabular-nums flex-shrink-0 ${
                    isActive ? "text-[#58a6ff]" : "text-[#484f58]"
                  }`}
                >
                  {num}
                </span>
                <span className="text-xs font-medium truncate">{label}</span>
              </button>
            );
          })}
        </nav>

        {/* Sidebar footer */}
        <div className="px-4 py-3 border-t border-[#21262d]">
          <p className="text-[10px] text-[#484f58]">
            ArchMind AI · v{report.schema_version}
          </p>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 px-5 lg:px-8 pb-20">

        {/* Back link */}
        <div className="pt-5 pb-1">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-[#6e7681] hover:text-[#58a6ff] transition-colors"
          >
            <svg
              width="12" height="12"
              viewBox="0 0 16 16" fill="none"
              stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M15 8H1M8 1L1 8l7 7" />
            </svg>
            New analysis
          </Link>
        </div>

        {/* ── 01 Hero Header ──────────────────────────────────────────── */}
        <section id="hero" className="pt-4 pb-2">
          <div className="rounded-xl border border-[#30363d] bg-[#161b22] overflow-hidden">
            <div className="h-0.5 bg-gradient-to-r from-[#1f6feb] via-[#388bfd] to-[#7c3aed]" />
            <div className="p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h1 className="text-2xl font-bold text-[#e6edf3] break-all">
                    {report.repo_name}
                  </h1>
                  <a
                    href={report.repo_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 text-sm text-[#58a6ff] hover:underline truncate block"
                  >
                    {report.repo_url}
                  </a>
                </div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[#1a3d1a] text-[#3fb950] border border-[#2d6a2d] flex-shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950] inline-block animate-pulse" />
                  Analysis Complete
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-[#8b949e]">
                <span>
                  <span className="text-[#6e7681]">Generated </span>
                  {new Date(report.generated_at).toLocaleString()}
                </span>
                <span>
                  <span className="text-[#6e7681]">Report </span>
                  <code className="font-mono">{report.report_id.slice(0, 8)}…</code>
                </span>
                <span>
                  <span className="text-[#6e7681]">Duration </span>
                  {metadata.analysis_duration_seconds.toFixed(1)}s
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ── 02 Key Metrics ──────────────────────────────────────────── */}
        <section id="kpi" className="pt-8">
          <SectionHeading number="02" title="Key Metrics" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              label="Architecture"
              value={metadata.detected_architecture_pattern}
              sub={`${metadata.primary_language} · ${metadata.total_files_analyzed} files`}
              accent="blue"
            />
            <KpiCard
              label="Confidence"
              value={confidence || "—"}
              sub={`${metadata.rag_chunks_used_count} knowledge chunks`}
              accent={
                confidence === "HIGH"
                  ? "green"
                  : confidence === "MEDIUM"
                  ? "yellow"
                  : "red"
              }
            />
            <KpiCard
              label="Security Findings"
              value={String(totalFindings)}
              sub={
                metadata.highest_severity_finding
                  ? `Highest: ${metadata.highest_severity_finding}`
                  : "No findings detected"
              }
              accent={
                totalFindings === 0
                  ? "green"
                  : metadata.highest_severity_finding === "CRITICAL"
                  ? "red"
                  : "orange"
              }
            />
            <KpiCard
              label="Recommendations"
              value={String(metadata.recommendation_count)}
              sub={`${metadata.p1_recommendation_count} high priority`}
              accent={metadata.p1_recommendation_count > 0 ? "orange" : "green"}
            />
          </div>
        </section>

        {/* ── 03 Executive Summary ────────────────────────────────────── */}
        {sectionMap["EXECUTIVE_SUMMARY"] && (
          <section id="executive-summary" className="pt-8">
            <SectionHeading number="03" title="Executive Summary" />
            <Card>
              <MarkdownContent content={sectionMap["EXECUTIVE_SUMMARY"]} />
            </Card>
          </section>
        )}

        {/* ── 04 Architecture Assessment ──────────────────────────────── */}
        <section id="architecture" className="pt-8">
          <SectionHeading number="04" title="Architecture Assessment" />
          <Card>
            {/* Confidence bar */}
            <div className="mb-5 pb-5 border-b border-[#21262d]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-[#6e7681]">
                  Pattern Confidence
                </span>
                <span className={`text-sm font-bold ${confStyle.text}`}>
                  {confidence || "UNKNOWN"}
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-[#21262d]">
                <div
                  className={`h-1.5 rounded-full transition-all duration-700 ${confStyle.bar} ${confStyle.width}`}
                />
              </div>
              <p className="mt-2 text-xs text-[#8b949e]">
                Detected pattern:{" "}
                <span className="text-[#cdd9e5] font-medium">
                  {metadata.detected_architecture_pattern}
                </span>
              </p>
            </div>
            {sectionMap["ARCHITECTURE_ASSESSMENT"] && (
              <MarkdownContent content={sectionMap["ARCHITECTURE_ASSESSMENT"]} />
            )}
          </Card>
        </section>

        {/* ── 05 Security Risk Assessment ─────────────────────────────── */}
        <section id="security" className="pt-8">
          <SectionHeading number="05" title="Security Risk Assessment" />
          <Card>
            {/* Donut + severity bars */}
            <div className="flex flex-col sm:flex-row gap-6 mb-5 pb-5 border-b border-[#21262d]">
              <div className="flex-shrink-0 flex items-center justify-center sm:justify-start">
                <DonutChart
                  counts={metadata.finding_counts_by_severity}
                  total={totalFindings}
                />
              </div>
              <div className="flex-1">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[#6e7681] mb-3">
                  Severity Distribution
                </p>
                <div className="space-y-2.5">
                  {SEVERITY_ORDER.map(sev => {
                    const count = metadata.finding_counts_by_severity[sev] ?? 0;
                    const pct = totalFindings > 0 ? (count / totalFindings) * 100 : 0;
                    const { dot, text, bg, border } = SEV_STYLES[sev];
                    return (
                      <div key={sev} className="flex items-center gap-3">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold border flex-shrink-0 w-32 ${bg} ${text} ${border}`}
                        >
                          <span
                            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                            style={{ background: dot }}
                          />
                          {sev}
                        </span>
                        <div className="flex-1 h-1.5 rounded-full bg-[#21262d]">
                          <div
                            className="h-1.5 rounded-full transition-all duration-700"
                            style={{ width: `${pct}%`, background: dot }}
                          />
                        </div>
                        <span className="text-xs tabular-nums w-4 text-right text-[#8b949e]">
                          {count}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            {sectionMap["SECURITY_FINDINGS"] && (
              <MarkdownContent content={sectionMap["SECURITY_FINDINGS"]} />
            )}
          </Card>
        </section>

        {/* ── 06 Analysis Pipeline ────────────────────────────────────── */}
        <section id="pipeline" className="pt-8">
          <SectionHeading number="06" title="Analysis Pipeline" />
          <Card>
            <div className="space-y-3">
              {PIPELINE_STAGES.map(stage => (
                <div key={stage} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-[#1a3d1a] border border-[#2d6a2d] flex items-center justify-center flex-shrink-0">
                    <svg
                      width="10" height="10" viewBox="0 0 12 12"
                      fill="none" aria-hidden="true"
                    >
                      <path
                        d="M2 6l3 3 5-5"
                        stroke="#3fb950"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                  <div className="flex-1 flex items-center justify-between">
                    <span className="text-sm text-[#cdd9e5] font-medium">{stage}</span>
                    <span className="text-[10px] text-[#3fb950] font-semibold tracking-wide">
                      COMPLETE
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-5 text-[11px] text-[#484f58] italic border-t border-[#21262d] pt-4">
              Individual stage timing is not stored in the report output. All stages
              shown as complete based on report existence.
            </p>
          </Card>
        </section>

        {/* ── 07 Repository Overview ──────────────────────────────────── */}
        <section id="repository" className="pt-8">
          <SectionHeading number="07" title="Repository Overview" />
          <Card>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5 pb-5 border-b border-[#21262d]">
              <MetaChip label="Language"      value={metadata.primary_language} />
              <MetaChip label="Files"         value={String(metadata.total_files_analyzed)} />
              <MetaChip label="LLM Tokens"    value={metadata.total_llm_tokens_used.toLocaleString()} />
              <MetaChip label="Duration"      value={`${metadata.analysis_duration_seconds.toFixed(1)}s`} />
              <MetaChip label="RAG Chunks"    value={String(metadata.rag_chunks_used_count)} />
              <MetaChip label="Schema"        value={`v${report.schema_version}`} />
            </div>
            {sectionMap["REPOSITORY_OVERVIEW"] && (
              <MarkdownContent content={sectionMap["REPOSITORY_OVERVIEW"]} />
            )}
          </Card>
        </section>

        {/* ── 08 Recommendations ──────────────────────────────────────── */}
        {sectionMap["RECOMMENDATIONS"] && (
          <section id="recommendations" className="pt-8">
            <SectionHeading number="08" title="Recommendations" />
            <Card>
              {metadata.p1_recommendation_count > 0 && (
                <div className="flex items-center gap-2 mb-4 px-3 py-2.5 rounded-lg bg-[#2d1e0f] border border-[#5c3a1a]">
                  <svg
                    width="14" height="14" viewBox="0 0 16 16"
                    fill="none" aria-hidden="true"
                  >
                    <path
                      d="M8 1L15 14H1L8 1z"
                      fill="#db6d28"
                      fillOpacity="0.2"
                      stroke="#db6d28"
                      strokeWidth="1.5"
                    />
                    <line x1="8" y1="6" x2="8" y2="10" stroke="#db6d28" strokeWidth="1.5" strokeLinecap="round" />
                    <circle cx="8" cy="12.5" r="0.75" fill="#db6d28" />
                  </svg>
                  <span className="text-xs text-[#db6d28] font-medium">
                    {metadata.p1_recommendation_count} high-priority{" "}
                    {metadata.p1_recommendation_count === 1
                      ? "recommendation requires"
                      : "recommendations require"}{" "}
                    immediate attention
                  </span>
                </div>
              )}
              <MarkdownContent content={sectionMap["RECOMMENDATIONS"]} />
            </Card>
          </section>
        )}

        {/* ── 09 Actionable Next Steps ────────────────────────────────── */}
        {sectionMap["ACTIONABLE_NEXT_STEPS"] && (
          <section id="next-steps" className="pt-8">
            <SectionHeading number="09" title="Actionable Next Steps" />
            <Card>
              <MarkdownContent content={sectionMap["ACTIONABLE_NEXT_STEPS"]} />
            </Card>
          </section>
        )}

        {/* ── 10 Export & Sharing ─────────────────────────────────────── */}
        <section id="export" className="pt-8">
          <SectionHeading number="10" title="Export & Sharing" />
          <Card>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[#21262d] text-[#cdd9e5] border border-[#30363d] hover:bg-[#30363d] hover:border-[#484f58] transition-colors"
              >
                <svg
                  width="14" height="14" viewBox="0 0 16 16"
                  fill="none" stroke="currentColor"
                  strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M4 6V1h8v5M4 11H2a1 1 0 01-1-1V7a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-1 1h-2" />
                  <rect x="4" y="10" width="8" height="5" />
                </svg>
                Print Report
              </button>
              <CopyLinkButton />
            </div>
            <p className="mt-4 text-xs text-[#484f58]">
              Report ID:{" "}
              <code className="font-mono text-[#6e7681]">{report.report_id}</code>
            </p>
          </Card>
        </section>

      </div>
    </div>
  );
}

// ── Shared sub-components ─────────────────────────────────────────────────────

function SectionHeading({ number, title }: { number: string; title: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <span className="text-[10px] font-mono text-[#484f58] flex-shrink-0">{number}</span>
      <h2 className="text-base font-semibold text-[#e6edf3] tracking-tight flex-shrink-0">
        {title}
      </h2>
      <div className="flex-1 h-px bg-[#21262d]" />
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5">
      {children}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  accent: Accent;
}) {
  const { val } = ACCENT[accent];
  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-[#6e7681] mb-2">
        {label}
      </p>
      <p className={`text-lg font-bold truncate ${val}`}>{value}</p>
      <p className="text-[11px] text-[#6e7681] mt-1 truncate">{sub}</p>
    </div>
  );
}

function MetaChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#21262d] bg-[#0d1117] px-3 py-2">
      <p className="text-[10px] text-[#6e7681] uppercase tracking-wide">{label}</p>
      <p className="text-sm font-medium text-[#cdd9e5] truncate mt-0.5">{value}</p>
    </div>
  );
}

function CopyLinkButton() {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard
      .writeText(window.location.href)
      .then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {});
  }

  return (
    <button
      onClick={copy}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[#21262d] text-[#cdd9e5] border border-[#30363d] hover:bg-[#30363d] hover:border-[#484f58] transition-colors"
    >
      <svg
        width="14" height="14" viewBox="0 0 16 16"
        fill="none" stroke="currentColor"
        strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="5" y="5" width="9" height="9" rx="1" />
        <path d="M2 11V2h9" />
      </svg>
      {copied ? "Copied!" : "Copy Link"}
    </button>
  );
}
