import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ArchMind AI",
  description: "AI-powered software architecture review",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-gray-50 text-gray-900 min-h-screen flex flex-col`}
      >
        {/* Header */}
        <header className="bg-white border-b border-gray-200">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-2.5">
            {/* favicon.svg is a 32×32 hexagon — correct asset for compact header mark */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/favicon.svg"
              alt=""
              aria-hidden="true"
              className="h-7 w-7 flex-shrink-0"
            />
            <span className="font-semibold text-base tracking-tight text-gray-900 select-none">
              ArchMind AI
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 flex flex-col">{children}</main>

        <footer className="border-t border-gray-100 py-5 text-center text-xs text-gray-400">
          ArchMind AI — Architecture Review Platform
        </footer>
      </body>
    </html>
  );
}
