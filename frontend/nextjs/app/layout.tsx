import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import ConditionalFooter from "./ConditionalFooter";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ArchMind AI",
  description: "AI-powered software architecture review",
};

function LogoMark() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="layoutLogoGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      <polygon points="16,2 28,9 28,23 16,30 4,23 4,9" fill="url(#layoutLogoGrad)" />
      <polygon
        points="16,8 22,12 22,20 16,24 10,20 10,12"
        fill="none"
        stroke="rgba(255,255,255,0.4)"
        strokeWidth="0.9"
      />
      <line x1="16" y1="2" x2="16" y2="30" stroke="rgba(255,255,255,0.15)" strokeWidth="0.7" />
      <line x1="4" y1="9" x2="28" y2="23" stroke="rgba(255,255,255,0.15)" strokeWidth="0.7" />
      <line x1="28" y1="9" x2="4" y2="23" stroke="rgba(255,255,255,0.15)" strokeWidth="0.7" />
      <circle cx="16" cy="16" r="3" fill="rgba(255,255,255,0.7)" />
    </svg>
  );
}

function GitHubNavIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
    </svg>
  );
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[#060a14] text-white min-h-screen flex flex-col`}
      >
        {/* Header — dark, minimal, full-width */}
        <header className="border-b border-[#1a3060]/40 bg-[#060a14]/90 backdrop-blur-sm sticky top-0 z-50">
          <div className="w-full max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <LogoMark />
              <span className="font-semibold text-[15px] tracking-tight text-white select-none">
                ArchMind AI
              </span>
            </div>
            <a
              href="https://github.com/arafat-ds/AI_Software_Architecture_Review_Agent-ArchMind.AI-"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#64748b] hover:text-white transition-colors duration-200"
              aria-label="View on GitHub"
            >
              <GitHubNavIcon />
            </a>
          </div>
        </header>

        <main className="flex-1 flex flex-col">{children}</main>

        {/* Footer hidden on landing page, visible on all other pages */}
        <ConditionalFooter />
      </body>
    </html>
  );
}
