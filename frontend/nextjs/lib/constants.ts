export const POLL_INTERVAL_MS = 5_000;
export const MAX_POLL_DURATION_MS = 1_800_000; // 30 min

export const SECTION_ORDER = [
  "EXECUTIVE_SUMMARY",
  "REPOSITORY_OVERVIEW",
  "ARCHITECTURE_ASSESSMENT",
  "SECURITY_FINDINGS",
  "RECOMMENDATIONS",
  "ACTIONABLE_NEXT_STEPS",
] as const;

export const SEVERITY_ORDER = [
  "CRITICAL",
  "HIGH",
  "MEDIUM",
  "LOW",
  "INFORMATIONAL",
] as const;

export const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "text-red-600 bg-red-50 border-red-200",
  HIGH: "text-orange-600 bg-orange-50 border-orange-200",
  MEDIUM: "text-yellow-600 bg-yellow-50 border-yellow-200",
  LOW: "text-blue-600 bg-blue-50 border-blue-200",
  INFORMATIONAL: "text-gray-600 bg-gray-50 border-gray-200",
};
