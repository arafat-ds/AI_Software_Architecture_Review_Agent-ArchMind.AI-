"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import type { ReportResponse, ReportSection } from "@/types/archmind";
import { SECTION_ORDER } from "@/lib/constants";
import MetadataPanel from "./MetadataPanel";

const NAV_LABELS: Record<string, string> = {
  EXECUTIVE_SUMMARY: "Executive Summary",
  REPOSITORY_OVERVIEW: "Repository",
  ARCHITECTURE_ASSESSMENT: "Architecture",
  SECURITY_FINDINGS: "Security",
  RECOMMENDATIONS: "Recommendations",
  ACTIONABLE_NEXT_STEPS: "Next Steps",
};

interface Props {
  report: ReportResponse;
}

export default function ReportViewer({ report }: Props) {
  const sortedSections = [...report.sections].sort(
    (a, b) =>
      SECTION_ORDER.indexOf(a.section_key as (typeof SECTION_ORDER)[number]) -
      SECTION_ORDER.indexOf(b.section_key as (typeof SECTION_ORDER)[number])
  );

  const [activeSection, setActiveSection] = useState<string>(
    sortedSections[0]?.section_key ?? ""
  );
  const mobileNavRef = useRef<HTMLDivElement>(null);

  // Track active section by scroll position
  useEffect(() => {
    function handleScroll() {
      const threshold = window.innerHeight * 0.3;
      let current = sortedSections[0]?.section_key ?? "";
      for (const s of sortedSections) {
        const el = document.getElementById(s.section_key.toLowerCase());
        if (el && el.getBoundingClientRect().top <= threshold) {
          current = s.section_key;
        }
      }
      setActiveSection(current);
    }
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, [sortedSections]);

  // Keep active pill in view on mobile nav
  useEffect(() => {
    const nav = mobileNavRef.current;
    if (!nav) return;
    const activeEl = nav.querySelector<HTMLElement>("[data-active='true']");
    activeEl?.scrollIntoView({ inline: "center", behavior: "smooth", block: "nearest" });
  }, [activeSection]);

  function scrollToSection(sectionKey: string) {
    document
      .getElementById(sectionKey.toLowerCase())
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="max-w-6xl mx-auto flex gap-8">
      {/* ── Sticky sidebar (lg+) ─────────────────────────────── */}
      <nav aria-label="Report sections" className="hidden lg:block w-44 flex-shrink-0">
        <div className="sticky top-6">
          <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-widest text-gray-400">
            Sections
          </p>
          {sortedSections.map((s) => {
            const active = activeSection === s.section_key;
            return (
              <button
                key={s.section_key}
                data-active={active}
                onClick={() => scrollToSection(s.section_key)}
                className={[
                  "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
                  active
                    ? "bg-indigo-50 text-indigo-700 font-medium"
                    : "text-gray-500 hover:text-gray-800 hover:bg-gray-100",
                ].join(" ")}
              >
                {NAV_LABELS[s.section_key] ?? s.section_title}
              </button>
            );
          })}
        </div>
      </nav>

      {/* ── Main content ─────────────────────────────────────── */}
      <div className="flex-1 min-w-0">
        {/* Back link */}
        <div className="mb-5">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 hover:underline"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M15 8H1M8 1L1 8l7 7" />
            </svg>
            Analyze another repository
          </Link>
        </div>

        {/* Mobile horizontal pill nav (< lg) */}
        <div
          ref={mobileNavRef}
          aria-label="Report sections"
          className="lg:hidden flex gap-1.5 overflow-x-auto pb-2 mb-6"
          style={{ scrollbarWidth: "none" }}
        >
          {sortedSections.map((s) => {
            const active = activeSection === s.section_key;
            return (
              <button
                key={s.section_key}
                data-active={active}
                onClick={() => scrollToSection(s.section_key)}
                className={[
                  "flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                  active
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200",
                ].join(" ")}
              >
                {NAV_LABELS[s.section_key] ?? s.section_title}
              </button>
            );
          })}
        </div>

        <article className="space-y-10">
          {/* Report header */}
          <header className="space-y-2">
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              {report.repo_name}
            </h1>
            <p className="text-sm text-gray-500">
              Generated {new Date(report.generated_at).toLocaleString()} · Schema v
              {report.schema_version}
            </p>
            <a
              href={report.repo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-indigo-600 hover:underline"
            >
              {report.repo_url}
            </a>
          </header>

          {/* Metadata panel */}
          <section>
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Analysis Metadata
            </h2>
            <MetadataPanel metadata={report.metadata} />
          </section>

          {/* Report sections */}
          {sortedSections.map((section) => (
            <ReportSectionBlock key={section.section_key} section={section} />
          ))}
        </article>
      </div>
    </div>
  );
}

function ReportSectionBlock({ section }: { section: ReportSection }) {
  return (
    <section className="space-y-3" id={section.section_key.toLowerCase()}>
      <h2 className="text-xl font-semibold text-gray-800 border-b border-gray-200 pb-2">
        {section.section_title}
      </h2>
      <div className="prose prose-gray max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
        >
          {section.content_markdown}
        </ReactMarkdown>
      </div>
    </section>
  );
}
