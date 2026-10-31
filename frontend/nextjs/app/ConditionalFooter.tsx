"use client";

import { usePathname } from "next/navigation";

export default function ConditionalFooter() {
  const pathname = usePathname();
  if (pathname === "/") return null;
  return (
    <footer className="border-t border-gray-200 py-5 text-center text-xs text-gray-400 bg-white">
      ArchMind AI — Architecture Review Platform
    </footer>
  );
}
