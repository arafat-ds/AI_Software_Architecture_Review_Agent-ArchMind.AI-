import type { SeverityLevel } from "@/types/archmind";

const SEV_COLORS: Record<SeverityLevel, string> = {
  CRITICAL: "#f85149",
  HIGH: "#db6d28",
  MEDIUM: "#d29922",
  LOW: "#58a6ff",
  INFORMATIONAL: "#6e7681",
};

const SEVERITIES: SeverityLevel[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];

interface Props {
  counts: Record<SeverityLevel, number>;
  total: number;
}

export default function DonutChart({ counts, total }: Props) {
  const size = 140;
  const cx = size / 2;
  const cy = size / 2;
  const r = 48;
  const strokeWidth = 16;
  const circumference = 2 * Math.PI * r;

  if (total === 0) {
    return (
      <div className="flex flex-col items-center justify-center w-[140px] h-[140px]">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center"
          style={{ border: "6px solid #21262d" }}
        >
          <span className="text-[10px] text-[#6e7681] text-center leading-tight">No<br />findings</span>
        </div>
      </div>
    );
  }

  // Build segments: fraction-based offset accumulation
  let accumulatedFraction = 0;
  const segments = SEVERITIES
    .filter(s => (counts[s] ?? 0) > 0)
    .map(s => {
      const fraction = (counts[s] ?? 0) / total;
      const dash = fraction * circumference;
      const gap = circumference - dash;
      const startOffset = circumference - accumulatedFraction * circumference;
      accumulatedFraction += fraction;
      return { severity: s, dash, gap, startOffset };
    });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label="Severity distribution donut chart">
      {/* Background ring */}
      <circle
        cx={cx} cy={cy} r={r}
        fill="none"
        stroke="#21262d"
        strokeWidth={strokeWidth}
      />
      {/* Segments, each rotated -90° so first segment starts at top */}
      {segments.map(({ severity, dash, gap, startOffset }) => (
        <circle
          key={severity}
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke={SEV_COLORS[severity]}
          strokeWidth={strokeWidth}
          strokeDasharray={`${dash} ${gap}`}
          strokeDashoffset={startOffset}
          strokeLinecap="butt"
          style={{ transform: "rotate(-90deg)", transformOrigin: "50% 50%" }}
        />
      ))}
      {/* Center label */}
      <text x={cx} y={cy - 5} textAnchor="middle" fontSize="24" fontWeight="700" fill="#e6edf3">
        {total}
      </text>
      <text x={cx} y={cy + 11} textAnchor="middle" fontSize="9" fill="#6e7681" letterSpacing="1">
        FINDINGS
      </text>
    </svg>
  );
}
