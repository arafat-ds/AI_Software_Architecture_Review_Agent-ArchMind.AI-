"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import SubmitForm from "@/components/SubmitForm";

// ─── Dot-grid decoration ────────────────────────────────────────────────────
function DotGrid({
  rows = 5,
  cols = 8,
  className = "",
}: {
  rows?: number;
  cols?: number;
  className?: string;
}) {
  const gap = 14;
  const r = 1.5;
  return (
    <svg
      width={cols * gap}
      height={rows * gap}
      viewBox={`0 0 ${cols * gap} ${rows * gap}`}
      className={className}
      aria-hidden="true"
    >
      {Array.from({ length: rows }, (_, row) =>
        Array.from({ length: cols }, (_, col) => (
          <circle
            key={`${row}-${col}`}
            cx={col * gap + gap / 2}
            cy={row * gap + gap / 2}
            r={r}
            fill="#6366f1"
          />
        ))
      )}
    </svg>
  );
}

// ─── GitHub repository card illustration ────────────────────────────────────
function GitHubIllustration() {
  return (
    <div className="relative select-none" aria-hidden="true">
      {/* Card */}
      <div className="w-48 bg-white rounded-2xl shadow-md border border-gray-100 p-4">
        {/* Header row */}
        <div className="flex items-center gap-2.5 mb-3.5">
          <div className="w-9 h-9 bg-gray-900 rounded-full flex items-center justify-center flex-shrink-0">
            {/* GitHub mark */}
            <svg
              viewBox="0 0 24 24"
              fill="white"
              width="18"
              height="18"
              aria-hidden="true"
            >
              <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
            </svg>
          </div>
          <div className="flex-1 space-y-1.5">
            <div className="h-2 bg-gray-700 rounded-full w-20" />
            <div className="h-1.5 bg-gray-200 rounded-full w-14" />
          </div>
        </div>
        {/* Simulated code lines */}
        <div className="space-y-2">
          <div className="h-2 bg-indigo-100 rounded-full w-full" />
          <div className="h-2 bg-gray-100 rounded-full w-10/12" />
          <div className="h-2 bg-gray-100 rounded-full w-7/12" />
          <div className="h-2 bg-indigo-50 rounded-full w-11/12" />
          <div className="h-2 bg-gray-100 rounded-full w-8/12" />
        </div>
      </div>

      {/* Network node lines below card */}
      <svg
        className="absolute -bottom-10 left-4 w-40 h-14"
        viewBox="0 0 160 56"
        aria-hidden="true"
      >
        <line x1="24" y1="0" x2="24" y2="28" stroke="#818cf8" strokeWidth="1.2" opacity="0.55" />
        <line x1="24" y1="28" x2="64" y2="48" stroke="#818cf8" strokeWidth="1.2" opacity="0.5" />
        <line x1="24" y1="28" x2="120" y2="44" stroke="#818cf8" strokeWidth="1.2" opacity="0.4" />
        <circle cx="24" cy="28" r="4" fill="#818cf8" opacity="0.65" />
        <circle cx="64" cy="48" r="3" fill="#a5b4fc" opacity="0.7" />
        <circle cx="120" cy="44" r="3" fill="#a5b4fc" opacity="0.55" />
        <circle cx="24" cy="0" r="2.5" fill="#6366f1" opacity="0.45" />
      </svg>
    </div>
  );
}

// ─── Security shield illustration ───────────────────────────────────────────
function ShieldIllustration() {
  return (
    <div
      className="relative select-none"
      style={{ width: 140, height: 160 }}
      aria-hidden="true"
    >
      {/* Shield SVG */}
      <svg viewBox="0 0 140 160" width="140" height="160" fill="none">
        {/* Outer halo */}
        <path
          d="M70 6 L128 32 L128 92 Q128 136 70 154 Q12 136 12 92 L12 32 Z"
          fill="#dde6ff"
          opacity="0.55"
        />
        {/* Mid ring */}
        <path
          d="M70 18 L118 42 L118 90 Q118 128 70 144 Q22 128 22 90 L22 42 Z"
          fill="#c7d7fd"
          opacity="0.65"
        />
        {/* Inner shield body */}
        <path
          d="M70 30 L108 50 L108 88 Q108 120 70 134 Q32 120 32 88 L32 50 Z"
          fill="#a5b4fc"
          opacity="0.55"
        />
        {/* Padlock body */}
        <rect x="52" y="80" width="36" height="28" rx="5" fill="#6366f1" opacity="0.82" />
        {/* Padlock shackle */}
        <path
          d="M62 80 L62 71 Q62 59 70 59 Q78 59 78 71 L78 80"
          stroke="#6366f1"
          strokeWidth="5"
          fill="none"
          strokeLinecap="round"
          opacity="0.88"
        />
        {/* Keyhole dot */}
        <circle cx="70" cy="91" r="4.5" fill="white" opacity="0.95" />
        <rect x="68.5" y="94" width="3" height="7" rx="1.5" fill="white" opacity="0.95" />
      </svg>

      {/* Connection dots positioned around the shield */}
      <div className="absolute top-10 -left-5 w-2.5 h-2.5 rounded-full bg-indigo-400 opacity-65" />
      <div className="absolute top-8 -right-5 w-2 h-2 rounded-full bg-indigo-300 opacity-60" />
      <div className="absolute bottom-10 -right-7 w-3.5 h-3.5 rounded-full bg-indigo-400 opacity-50" />

      {/* Short connector lines from dots to shield edge */}
      <svg className="absolute inset-0 w-full h-full overflow-visible" aria-hidden="true">
        <line x1="-5" y1="50" x2="18" y2="62" stroke="#818cf8" strokeWidth="1" opacity="0.4" />
        <line x1="145" y1="46" x2="118" y2="56" stroke="#818cf8" strokeWidth="1" opacity="0.4" />
        <line x1="147" y1="118" x2="120" y2="108" stroke="#818cf8" strokeWidth="1" opacity="0.35" />
      </svg>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function HomePage() {
  const router = useRouter();
  const [submitted, setSubmitted] = useState(false);

  function handleJobSubmitted(jobId: string) {
    setSubmitted(true);
    router.push(`/jobs/${jobId}`);
  }

  return (
    <div className="flex-1 flex flex-col">
      {/*
       * Single section — gradient background covers hero, form, and notice.
       * flex-1 ensures it fills all space between header and footer.
       */}
      <section
        className="flex-1 relative overflow-hidden"
        style={{
          background: [
            "radial-gradient(ellipse at 80% 0%, rgba(255,255,255,0.75) 0%, transparent 45%)",
            "radial-gradient(ellipse at 5% 55%, rgba(196,210,255,0.4) 0%, transparent 50%)",
            "linear-gradient(150deg, #eef2ff 0%, #e8eeff 35%, #f0ebff 65%, #edf4ff 100%)",
          ].join(", "),
        }}
      >
        {/* ── Background decorations (non-interactive) ─────────────── */}

        {/* Dot grids */}
        <DotGrid
          rows={5}
          cols={8}
          className="absolute top-8 left-8 opacity-[0.17] hidden sm:block"
        />
        <DotGrid
          rows={4}
          cols={5}
          className="absolute top-6 right-14 opacity-[0.11] hidden md:block"
        />

        {/* Flowing wave curves */}
        <svg
          className="absolute bottom-0 left-0 w-full opacity-[0.07] pointer-events-none"
          viewBox="0 0 1440 200"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path
            d="M0 80 Q360 20 720 100 Q1080 180 1440 80"
            stroke="#6366f1"
            strokeWidth="2"
            fill="none"
          />
          <path
            d="M0 130 Q400 50 800 130 Q1100 200 1440 120"
            stroke="#8b5cf6"
            strokeWidth="1.5"
            fill="none"
          />
        </svg>

        {/* ── Hero: illustrations + headline + chips ────────────────── */}
        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 pt-8 pb-4 sm:pt-12 sm:pb-6">
          <div className="grid grid-cols-1 xl:grid-cols-[160px_1fr_160px] gap-4 items-center">

            {/* Left — GitHub card (wide desktop only) */}
            <div className="hidden xl:flex items-center justify-end pr-6">
              <GitHubIllustration />
            </div>

            {/* Center — headline + subtitle + chips */}
            <div className="text-center space-y-4 py-2">
              <h1 className="text-3xl sm:text-[2.5rem] lg:text-5xl font-bold leading-tight tracking-tight">
                <span className="block text-gray-900 xl:whitespace-nowrap">
                  Understand Your Architecture.
                </span>
                <span className="block text-indigo-600 mt-1 xl:whitespace-nowrap">
                  Strengthen Your Security.
                </span>
              </h1>

              <p className="text-gray-500 text-base sm:text-lg max-w-sm mx-auto leading-relaxed">
                Analyze your GitHub repository to uncover architectural insights
                and security risks.
              </p>

              {/* Capability chips */}
              <div className="flex flex-wrap gap-2 justify-center pt-1">
                {[
                  "Architecture patterns",
                  "Security findings",
                  "AI recommendations",
                ].map((label) => (
                  <span
                    key={label}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white/70 border border-indigo-200 text-indigo-700 text-xs font-medium"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                    {label}
                  </span>
                ))}
              </div>
            </div>

            {/* Right — Shield (wide desktop only) */}
            <div className="hidden xl:flex items-center justify-start pl-6">
              <ShieldIllustration />
            </div>
          </div>
        </div>

        {/* ── Form + setup notice ───────────────────────────────────── */}
        <div className="relative z-10 max-w-2xl mx-auto px-4 sm:px-6 pb-8 sm:pb-12 space-y-4">

          {/* Submission card */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 sm:p-8">
            {submitted ? (
              <p className="text-center text-gray-500 py-4">
                Redirecting to job status…
              </p>
            ) : (
              <SubmitForm onJobSubmitted={handleJobSubmitted} />
            )}
          </div>

          {/* Setup notice */}
          <div className="flex gap-3 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3.5 text-sm text-amber-800">
            <span
              className="mt-0.5 flex-shrink-0 text-amber-500"
              aria-hidden="true"
            >
              ⓘ
            </span>
            <p>
              <span className="font-semibold">Setup required —</span> this
              instance must be configured with a backend API key by the server
              operator before analysis requests can be processed.
            </p>
          </div>

        </div>
      </section>
    </div>
  );
}
