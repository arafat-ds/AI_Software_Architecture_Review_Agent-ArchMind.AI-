"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { validateGitHubUrl } from "@/lib/validate";
import { submitJob } from "@/lib/api";

// ─── Icons ──────────────────────────────────────────────────────────────────

function GitHubInputIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
    </svg>
  );
}

// ─── Background ─────────────────────────────────────────────────────────────

function Background() {
  return (
    <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none" aria-hidden="true">
      {/* Radial glow — top right (blue/cyan) */}
      <div
        className="absolute -top-24 -right-24 w-[700px] h-[700px] rounded-full opacity-20"
        style={{
          background:
            "radial-gradient(circle, rgba(0,180,255,0.6) 0%, rgba(0,80,255,0.3) 40%, transparent 70%)",
        }}
      />
      {/* Radial glow — centre right (indigo) */}
      <div
        className="absolute top-1/3 right-0 w-[500px] h-[500px] rounded-full opacity-15"
        style={{
          background:
            "radial-gradient(circle, rgba(80,0,255,0.5) 0%, rgba(120,0,220,0.2) 50%, transparent 70%)",
        }}
      />
      {/* Radial glow — bottom left (purple) */}
      <div
        className="absolute bottom-0 -left-32 w-[500px] h-[400px] rounded-full opacity-15"
        style={{
          background:
            "radial-gradient(ellipse, rgba(139,0,255,0.4) 0%, rgba(80,0,200,0.15) 50%, transparent 70%)",
        }}
      />

      {/* Subtle dot-grid */}
      <div
        className="absolute inset-0 opacity-[0.045]"
        style={{
          backgroundImage:
            "radial-gradient(circle, #60a5fa 1px, transparent 1px)",
          backgroundSize: "36px 36px",
        }}
      />

      {/* Bottom flowing wave */}
      <svg
        className="absolute bottom-0 left-0 w-full opacity-30"
        viewBox="0 0 1440 180"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="waveGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0" />
            <stop offset="30%" stopColor="#0ea5e9" stopOpacity="0.8" />
            <stop offset="70%" stopColor="#6366f1" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="waveGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0" />
            <stop offset="40%" stopColor="#22d3ee" stopOpacity="0.5" />
            <stop offset="60%" stopColor="#818cf8" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M0 80 Q200 20 400 90 Q600 160 800 70 Q1000 0 1200 80 Q1320 130 1440 60 L1440 180 L0 180 Z"
          fill="url(#waveGrad1)"
          opacity="0.35"
        />
        <path
          d="M0 120 Q250 60 500 110 Q750 160 1000 90 Q1200 40 1440 100 L1440 180 L0 180 Z"
          fill="url(#waveGrad2)"
          opacity="0.25"
        />
        <path
          d="M0 100 Q360 30 720 110 Q1080 180 1440 80"
          stroke="url(#waveGrad1)"
          strokeWidth="1.5"
          fill="none"
          opacity="0.6"
        />
        <path
          d="M0 140 Q400 70 800 140 Q1100 200 1440 120"
          stroke="url(#waveGrad2)"
          strokeWidth="1"
          fill="none"
          opacity="0.5"
        />
      </svg>
    </div>
  );
}

// ─── Central hex cube ────────────────────────────────────────────────────────

function ArchMindCube() {
  return (
    <svg
      viewBox="0 0 200 242"
      width="190"
      height="228"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="hexBody" cx="42%" cy="38%">
          <stop offset="0%" stopColor="#bfdbfe" stopOpacity="0.35" />
          <stop offset="25%" stopColor="#38bdf8" stopOpacity="0.85" />
          <stop offset="60%" stopColor="#4f46e5" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#3b0764" stopOpacity="1" />
        </radialGradient>
        <radialGradient id="innerRing" cx="50%" cy="50%">
          <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.05" />
        </radialGradient>
        <filter id="hexGlow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="10" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id="platGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0" />
          <stop offset="25%" stopColor="#0ea5e9" stopOpacity="0.9" />
          <stop offset="50%" stopColor="#22d3ee" stopOpacity="1" />
          <stop offset="75%" stopColor="#0ea5e9" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Outer ambient glow ring */}
      <ellipse
        cx="100"
        cy="110"
        rx="82"
        ry="78"
        fill="none"
        stroke="#4f46e5"
        strokeWidth="1"
        opacity="0.25"
        filter="url(#hexGlow)"
      />

      {/* Main hex body */}
      <polygon
        points="100,22 168,62 168,142 100,182 32,142 32,62"
        fill="url(#hexBody)"
        filter="url(#hexGlow)"
      />

      {/* Neon hex border */}
      <polygon
        points="100,22 168,62 168,142 100,182 32,142 32,62"
        fill="none"
        stroke="#22d3ee"
        strokeWidth="1.5"
        opacity="0.75"
      />

      {/* Internal geometry lines (spokes to center) */}
      {[
        [100, 22], [168, 62], [168, 142], [100, 182], [32, 142], [32, 62],
      ].map(([x, y], i) => (
        <line
          key={i}
          x1={x}
          y1={y}
          x2="100"
          y2="102"
          stroke="#22d3ee"
          strokeWidth="0.7"
          opacity={i < 2 || i === 5 ? 0.5 : 0.35}
        />
      ))}

      {/* Inner hexagon ring */}
      <polygon
        points="100,58 130,75 130,109 100,126 70,109 70,75"
        fill="none"
        stroke="#818cf8"
        strokeWidth="1"
        opacity="0.55"
      />

      {/* Centre circle + logo mark */}
      <circle cx="100" cy="102" r="26" fill="url(#innerRing)" filter="url(#softGlow)" />
      <circle cx="100" cy="102" r="26" fill="none" stroke="#a78bfa" strokeWidth="1.5" opacity="0.8" />
      {/* ArchMind inner hex mark */}
      <polygon
        points="100,86 113,94 113,110 100,118 87,110 87,94"
        fill="none"
        stroke="rgba(255,255,255,0.85)"
        strokeWidth="1.5"
      />
      <circle cx="100" cy="102" r="4.5" fill="white" opacity="0.92" />

      {/* Platform glow base */}
      <ellipse cx="100" cy="200" rx="76" ry="9" fill="url(#platGrad)" />

      {/* Label */}
      <text
        x="100"
        y="225"
        textAnchor="middle"
        fill="#22d3ee"
        fontSize="13"
        fontFamily="var(--font-geist-sans), ui-sans-serif, sans-serif"
        fontWeight="600"
        letterSpacing="0.08em"
        opacity="0.9"
      >
        ArchMind AI
      </text>
    </svg>
  );
}

// ─── Feature card ────────────────────────────────────────────────────────────

function FeatureCard({
  icon,
  iconBg,
  title,
  desc,
  style,
}: {
  icon: React.ReactNode;
  iconBg: string;
  title: string;
  desc: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className="absolute w-[162px] rounded-xl p-3.5 backdrop-blur-sm"
      style={{
        background: "rgba(8,16,44,0.88)",
        border: "1px solid rgba(30,80,180,0.45)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
        ...style,
      }}
    >
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center mb-2.5 flex-shrink-0"
        style={{ background: iconBg }}
      >
        {icon}
      </div>
      <div className="text-white text-[11.5px] font-semibold leading-snug mb-1">{title}</div>
      <div className="text-[#64748b] text-[10px] leading-tight">{desc}</div>
    </div>
  );
}

// ─── Visualization (cube + cards + connection lines) ─────────────────────────

function ArchVisualization() {
  const cubeLeft = "calc(50% - 95px)";

  return (
    <div className="relative h-[400px]" aria-hidden="true">
      {/* Connection lines SVG (behind cards, above bg) */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox="0 0 600 400"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="connGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.15" />
            <stop offset="50%" stopColor="#22d3ee" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        {/* Top-left card → cube */}
        <line x1="162" y1="75" x2="245" y2="145" stroke="#22d3ee" strokeWidth="0.8" opacity="0.35" strokeDasharray="4 4" />
        {/* Top-right card → cube */}
        <line x1="438" y1="75" x2="355" y2="145" stroke="#22d3ee" strokeWidth="0.8" opacity="0.35" strokeDasharray="4 4" />
        {/* Mid-left card → cube */}
        <line x1="162" y1="230" x2="245" y2="200" stroke="#22d3ee" strokeWidth="0.8" opacity="0.3" strokeDasharray="4 4" />
        {/* Mid-right card → cube */}
        <line x1="438" y1="235" x2="355" y2="200" stroke="#22d3ee" strokeWidth="0.8" opacity="0.3" strokeDasharray="4 4" />
        {/* Corner connector dots */}
        <circle cx="162" cy="75" r="3" fill="#22d3ee" opacity="0.5" />
        <circle cx="438" cy="75" r="3" fill="#22d3ee" opacity="0.5" />
        <circle cx="162" cy="230" r="3" fill="#22d3ee" opacity="0.4" />
        <circle cx="438" cy="235" r="3" fill="#22d3ee" opacity="0.4" />
      </svg>

      {/* Central ArchMind cube */}
      <div className="absolute" style={{ left: cubeLeft, top: "30px" }}>
        <ArchMindCube />
      </div>

      {/* Architecture Analysis — top left */}
      <FeatureCard
        icon={
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="#22d3ee" strokeWidth="1.5">
            <path d="M6 5h1.5M6 8h3M6 11h5M4 3h12a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V4a1 1 0 011-1z" strokeLinecap="round" />
            <path d="M9 5l2 3-2 3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
        iconBg="rgba(14,165,233,0.18)"
        title="Architecture Analysis"
        desc="System design, patterns and structure"
        style={{ top: 20, left: 0 }}
      />

      {/* Code Quality Review — top right */}
      <FeatureCard
        icon={
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="#22d3ee" strokeWidth="1.5">
            <rect x="3" y="12" width="3" height="5" rx="0.5" fill="#22d3ee" stroke="none" />
            <rect x="8.5" y="8" width="3" height="9" rx="0.5" fill="#22d3ee" stroke="none" opacity="0.8" />
            <rect x="14" y="5" width="3" height="12" rx="0.5" fill="#22d3ee" stroke="none" opacity="0.6" />
          </svg>
        }
        iconBg="rgba(14,165,233,0.18)"
        title="Code Quality Review"
        desc="Maintainability, complexity and dependencies"
        style={{ top: 20, right: 0 }}
      />

      {/* Security Scanning — mid left */}
      <FeatureCard
        icon={
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="#a78bfa" strokeWidth="1.5">
            <path d="M10 2L4 5v5c0 3.5 2.5 6.5 6 7.5 3.5-1 6-4 6-7.5V5L10 2z" strokeLinejoin="round" />
            <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
        iconBg="rgba(139,92,246,0.18)"
        title="Security Scanning"
        desc="Vulnerabilities, risks and best practices"
        style={{ top: 185, left: 0 }}
      />

      {/* AI Recommendations — mid right */}
      <FeatureCard
        icon={
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="#fbbf24" strokeWidth="1.5">
            <path d="M10 2a5 5 0 015 5c0 2-1 3.5-2.5 4.5V13H7.5v-1.5C6 10.5 5 9 5 7a5 5 0 015-5z" strokeLinejoin="round" />
            <path d="M7.5 15.5h5M8.5 17.5h3" strokeLinecap="round" />
          </svg>
        }
        iconBg="rgba(251,191,36,0.15)"
        title="AI Recommendations"
        desc="Actionable insights and improvements"
        style={{ top: 195, right: 0 }}
      />
    </div>
  );
}

// ─── Dashboard preview panel ─────────────────────────────────────────────────

function DashboardPreview() {
  const stages = [
    "Repository Analysis",
    "Architecture Detection",
    "Security Analysis",
    "Code Quality Review",
    "Dependency Analysis",
    "AI Recommendations",
    "Report Generation",
  ];

  const nodes = [
    { id: "repo", label: "Repository\nAnalysis", x: 80, y: 55, active: true },
    { id: "arch", label: "Architecture\nDetection", x: 175, y: 115, active: true },
    { id: "sec", label: "Security\nAnalysis", x: 270, y: 55, active: false },
    { id: "qual", label: "Code Quality\nReview", x: 175, y: 185, active: false },
    { id: "ai", label: "AI\nRecommend.", x: 270, y: 155, active: false },
    { id: "report", label: "Report\nGeneration", x: 350, y: 100, active: false },
  ];

  const edges: [number, number][] = [[0, 1], [1, 2], [1, 3], [2, 4], [3, 4], [4, 5]];

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: "rgba(6,12,30,0.92)",
        border: "1px solid rgba(30,60,140,0.5)",
        boxShadow: "0 8px 40px rgba(0,0,30,0.6)",
      }}
    >
      {/* Window chrome */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: "rgba(30,60,140,0.4)" }}
      >
        <div className="w-3 h-3 rounded-full bg-red-500/70" />
        <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
        <div className="w-3 h-3 rounded-full bg-green-500/70" />
        <div className="ml-2 flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-gradient-to-br from-cyan-400 to-indigo-500" />
          <span className="text-white text-[11px] font-semibold">ArchMind AI</span>
        </div>
      </div>

      <div className="flex" style={{ height: 220 }}>
        {/* Left sidebar — stage list */}
        <div
          className="flex-shrink-0 w-40 py-2 overflow-hidden"
          style={{ borderRight: "1px solid rgba(30,60,140,0.35)" }}
        >
          {[
            { label: "Repository Analysis", active: true },
            ...stages.slice(1).map((s) => ({ label: s, active: false })),
          ].map(({ label, active }) => (
            <div
              key={label}
              className="flex items-center gap-2 px-3 py-1.5"
              style={{
                background: active ? "rgba(14,165,233,0.12)" : "transparent",
              }}
            >
              <div
                className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0"
                style={{ background: active ? "rgba(14,165,233,0.25)" : "rgba(255,255,255,0.05)" }}
              >
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ background: active ? "#22d3ee" : "#334155" }}
                />
              </div>
              <span
                className="text-[9.5px] leading-tight"
                style={{ color: active ? "#e2e8f0" : "#475569" }}
              >
                {label}
              </span>
            </div>
          ))}
        </div>

        {/* Centre — node graph */}
        <div className="flex-1 relative overflow-hidden">
          <svg viewBox="0 0 420 230" className="w-full h-full">
            <defs>
              <radialGradient id="nodeGrad" cx="50%" cy="50%">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.7" />
              </radialGradient>
            </defs>
            {edges.map(([a, b], i) => (
              <line
                key={i}
                x1={nodes[a].x}
                y1={nodes[a].y}
                x2={nodes[b].x}
                y2={nodes[b].y}
                stroke="#1e3a6e"
                strokeWidth="1.5"
              />
            ))}
            {nodes.map((n) => (
              <g key={n.id}>
                <circle
                  cx={n.x}
                  cy={n.y}
                  r="22"
                  fill={n.active ? "rgba(14,165,233,0.2)" : "rgba(30,58,138,0.3)"}
                  stroke={n.active ? "#38bdf8" : "#1e3a6e"}
                  strokeWidth="1.5"
                />
                {n.active && (
                  <circle cx={n.x} cy={n.y} r="26" fill="none" stroke="#38bdf8" strokeWidth="0.8" opacity="0.4" />
                )}
                <text
                  x={n.x}
                  y={n.y + 35}
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize="8"
                  fontFamily="sans-serif"
                >
                  {n.label.split("\n").map((line, li) => (
                    <tspan key={li} x={n.x} dy={li === 0 ? 0 : 10}>
                      {line}
                    </tspan>
                  ))}
                </text>
                {/* Icon inside node */}
                <circle cx={n.x} cy={n.y} r="8" fill={n.active ? "#0ea5e9" : "#1e3a6e"} />
              </g>
            ))}
          </svg>
        </div>

        {/* Right panel — progress + logs */}
        <div
          className="flex-shrink-0 w-44 p-3 space-y-3 overflow-hidden"
          style={{ borderLeft: "1px solid rgba(30,60,140,0.35)" }}
        >
          {/* Analysis Progress */}
          <div>
            <div className="text-[9px] text-[#94a3b8] mb-1 font-medium">Analysis Progress</div>
            <div className="text-[9px] text-[#64748b] mb-1.5">5/7 stages completed</div>
            <div className="h-1.5 rounded-full bg-[#0f172a] overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: "71%",
                  background: "linear-gradient(90deg, #0ea5e9, #a78bfa)",
                }}
              />
            </div>
            <div className="text-right text-[9px] text-[#22d3ee] mt-0.5">71%</div>
          </div>

          {/* Current Stage */}
          <div>
            <div className="text-[9px] text-[#94a3b8] mb-1 font-medium">Current Stage</div>
            <div className="text-[10px] text-white font-semibold">Security Analysis</div>
            <div className="text-[8.5px] text-[#64748b] mt-0.5">Scanning for vulnerabilities...</div>
          </div>

          {/* Live Logs */}
          <div>
            <div className="text-[9px] text-[#94a3b8] mb-1.5 font-medium">Live Logs</div>
            <div className="space-y-1">
              {[
                { dot: "#22d3ee", text: "Analyzing repository structure..." },
                { dot: "#22d3ee", text: "Detected Python project" },
                { dot: "#fbbf24", text: "Checking dependencies..." },
                { dot: "#34d399", text: "Running security analysis..." },
              ].map(({ dot, text }) => (
                <div key={text} className="flex items-start gap-1.5">
                  <div
                    className="w-1.5 h-1.5 rounded-full mt-0.5 flex-shrink-0"
                    style={{ background: dot }}
                  />
                  <span className="text-[8.5px] text-[#64748b] leading-tight">{text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Stats row ───────────────────────────────────────────────────────────────

const STATS = [
  {
    icon: (
      <svg viewBox="0 0 20 20" width="18" height="18" fill="none" aria-hidden="true">
        <path d="M10 2l1.8 5.5H17l-4.4 3.2 1.7 5.3L10 13l-4.3 3 1.7-5.3L3 7.5h5.2L10 2z"
          fill="#22d3ee" />
      </svg>
    ),
    iconBg: "rgba(14,165,233,0.15)",
    iconBorder: "rgba(14,165,233,0.3)",
    value: "7",
    label: "Analysis Stages",
    sub: "End-to-end analysis",
  },
  {
    icon: (
      <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="#60a5fa" strokeWidth="1.8" aria-hidden="true">
        <path d="M10 2L4 5v5c0 3.5 2.5 6.5 6 7.5 3.5-1 6-4 6-7.5V5L10 2z" strokeLinejoin="round" />
        <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    iconBg: "rgba(96,165,250,0.12)",
    iconBorder: "rgba(96,165,250,0.28)",
    value: "50+",
    label: "Security Checks",
    sub: "OWASP & best practices",
  },
  {
    icon: (
      <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="#818cf8" strokeWidth="1.8" aria-hidden="true">
        <rect x="3" y="3" width="6" height="6" rx="1" />
        <rect x="11" y="3" width="6" height="6" rx="1" />
        <rect x="3" y="11" width="6" height="6" rx="1" />
        <rect x="11" y="11" width="6" height="6" rx="1" />
      </svg>
    ),
    iconBg: "rgba(129,140,248,0.12)",
    iconBorder: "rgba(129,140,248,0.28)",
    value: "AI",
    label: "Powered Insights",
    sub: "LLM + Code Analysis",
  },
  {
    icon: (
      <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="#c084fc" strokeWidth="1.8" aria-hidden="true">
        <path d="M4 4h12v2H4zM4 8h12v2H4zM4 12h8v2H4z" strokeLinecap="round" />
        <path d="M3 3h14a1 1 0 011 1v12a1 1 0 01-1 1H3a1 1 0 01-1-1V4a1 1 0 011-1z" />
      </svg>
    ),
    iconBg: "rgba(192,132,252,0.12)",
    iconBorder: "rgba(192,132,252,0.28)",
    value: "Detailed",
    label: "Reports",
    sub: "Actionable recommendations",
  },
];

function StatsRow() {
  return (
    <div
      className="grid grid-cols-2 lg:grid-cols-4 gap-px mt-10 rounded-xl overflow-hidden"
      style={{
        background: "rgba(30,60,120,0.2)",
        border: "1px solid rgba(30,80,160,0.3)",
      }}
    >
      {STATS.map((s, i) => (
        <div
          key={i}
          className="flex items-center gap-3.5 px-5 py-4"
          style={{ background: "rgba(6,12,30,0.6)" }}
        >
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: s.iconBg, border: `1px solid ${s.iconBorder}` }}
          >
            {s.icon}
          </div>
          <div>
            <div className="text-white font-bold text-lg leading-none">{s.value}</div>
            <div className="text-[#94a3b8] text-[11px] mt-0.5">{s.label}</div>
            <div className="text-[#475569] text-[10px] mt-0.5">{s.sub}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setUrl(e.target.value);
    if (validationError) setValidationError(null);
    if (submitError) setSubmitError(null);
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const err = validateGitHubUrl(url);
    if (err) {
      setValidationError(err);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await submitJob({ repo_url: url.trim() });
      setSubmitted(true);
      router.push(`/jobs/${result.job_id}`);
    } catch (ex) {
      setSubmitError(ex instanceof Error ? ex.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  const isEmpty = !url.trim();
  const isDisabled = submitting || isEmpty;

  return (
    <div className="flex-1 relative overflow-hidden bg-[#060a14]">
      <Background />

      <div className="relative z-10 w-full max-w-[1380px] mx-auto px-6 md:px-10 pt-10 pb-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 xl:gap-16 items-start">

          {/* ─── Left column ─────────────────────────────────────── */}
          <div className="pt-4 lg:pt-8 space-y-7">

            {/* Badge */}
            <span
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-[12px] font-medium text-cyan-300"
              style={{
                background: "rgba(6,182,212,0.08)",
                border: "1px solid rgba(6,182,212,0.3)",
              }}
            >
              <svg viewBox="0 0 16 16" width="12" height="12" fill="#22d3ee" aria-hidden="true">
                <path d="M8 1l1.5 4.5H14l-3.7 2.7 1.4 4.3L8 10 4.3 12.5l1.4-4.3L2 5.5h4.5L8 1z" />
              </svg>
              AI-Powered Code Architecture Analysis
            </span>

            {/* Headline */}
            <div>
              <h1 className="text-4xl sm:text-5xl xl:text-[3.4rem] font-bold leading-[1.12] tracking-tight text-white">
                Understand Your
                <br />
                Architecture.
              </h1>
              <h1
                className="text-4xl sm:text-5xl xl:text-[3.4rem] font-bold leading-[1.12] tracking-tight mt-1"
                style={{
                  background: "linear-gradient(95deg, #22d3ee 0%, #818cf8 50%, #c084fc 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                Strengthen Your Security.
              </h1>
            </div>

            {/* Subtext */}
            <p className="text-[#94a3b8] text-base sm:text-[17px] leading-relaxed max-w-[490px]">
              Analyze your GitHub repository with AI to uncover architectural
              insights, security risks, and actionable recommendations for
              better, more maintainable systems.
            </p>

            {/* Form panel */}
            <div
              className="rounded-2xl p-6"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.1)",
                backdropFilter: "blur(12px)",
              }}
            >
              {submitted ? (
                <p className="text-center text-[#94a3b8] py-4">Redirecting to job status…</p>
              ) : (
                <form onSubmit={handleSubmit} noValidate>
                  <label
                    htmlFor="repo-url"
                    className="block text-sm font-semibold text-white mb-3"
                  >
                    GitHub Repository URL
                  </label>

                  {/* Input row */}
                  <div className="flex gap-3">
                    <div className="flex-1 relative">
                      <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#64748b]">
                        <GitHubInputIcon />
                      </div>
                      <input
                        id="repo-url"
                        type="url"
                        value={url}
                        onChange={handleChange}
                        placeholder="https://github.com/owner/repo"
                        disabled={submitting}
                        autoComplete="url"
                        className="w-full pl-10 pr-4 py-3 rounded-xl text-sm text-white placeholder:text-[#475569] focus:outline-none disabled:cursor-not-allowed"
                        style={{
                          background: validationError
                            ? "rgba(239,68,68,0.08)"
                            : "rgba(255,255,255,0.06)",
                          border: validationError
                            ? "1px solid rgba(239,68,68,0.5)"
                            : "1px solid rgba(255,255,255,0.12)",
                          boxShadow: "inset 0 1px 3px rgba(0,0,0,0.3)",
                        }}
                        aria-describedby={
                          validationError ? "url-error" : submitError ? "submit-error" : undefined
                        }
                        aria-invalid={!!validationError}
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={isDisabled}
                      className="flex-shrink-0 px-5 py-3 rounded-xl text-sm font-semibold text-white transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                      style={
                        isDisabled
                          ? {
                              background: "rgba(255,255,255,0.08)",
                              border: "1px solid rgba(255,255,255,0.1)",
                              color: "#475569",
                              cursor: "not-allowed",
                            }
                          : {
                              background:
                                "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)",
                              border: "1px solid rgba(139,92,246,0.5)",
                              boxShadow: "0 4px 20px rgba(124,58,237,0.4)",
                              cursor: "pointer",
                            }
                      }
                    >
                      {submitting ? (
                        <span className="inline-flex items-center gap-2">
                          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                          </svg>
                          Submitting…
                        </span>
                      ) : (
                        "Analyze Repository →"
                      )}
                    </button>
                  </div>

                  {validationError && (
                    <p id="url-error" className="mt-2 text-xs text-red-400" role="alert">
                      {validationError}
                    </p>
                  )}
                  {submitError && (
                    <p id="submit-error" className="mt-2 text-xs text-red-400" role="alert">
                      {submitError}
                    </p>
                  )}

                  {/* Trust indicators */}
                  <div className="flex flex-wrap gap-x-5 gap-y-2 mt-4 pt-4" style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                    {[
                      {
                        icon: (
                          <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="#60a5fa" strokeWidth="1.5">
                            <rect x="3" y="7" width="10" height="8" rx="1" />
                            <path d="M5 7V5a3 3 0 016 0v2" strokeLinecap="round" />
                          </svg>
                        ),
                        label: "Public & private repositories",
                      },
                      {
                        icon: (
                          <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="#60a5fa" strokeWidth="1.5">
                            <path d="M8 1.5L2.5 4v4c0 3 2.2 5.6 5.5 6.5 3.3-.9 5.5-3.5 5.5-6.5V4L8 1.5z" />
                          </svg>
                        ),
                        label: "Secure analysis",
                      },
                      {
                        icon: (
                          <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="#60a5fa" strokeWidth="1.5">
                            <rect x="2" y="1" width="12" height="14" rx="1.5" />
                            <path d="M5 5h6M5 8h6M5 11h4" strokeLinecap="round" />
                          </svg>
                        ),
                        label: "Detailed AI-powered report",
                      },
                    ].map(({ icon, label }) => (
                      <span key={label} className="inline-flex items-center gap-1.5 text-[11.5px] text-[#64748b]">
                        {icon}
                        {label}
                      </span>
                    ))}
                  </div>
                </form>
              )}
            </div>
          </div>

          {/* ─── Right column ─────────────────────────────────────── */}
          <div className="hidden lg:block pt-2">
            <ArchVisualization />
            <DashboardPreview />
          </div>

        </div>

        {/* Stats row */}
        <StatsRow />
      </div>
    </div>
  );
}
