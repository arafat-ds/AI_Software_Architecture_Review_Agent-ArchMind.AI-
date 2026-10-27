import type { ReportMetadata } from "@/types/archmind";
import { SEVERITY_ORDER, SEVERITY_COLORS } from "@/lib/constants";

interface Props {
  metadata: ReportMetadata;
}

export default function MetadataPanel({ metadata }: Props) {
  const highestSeverity = metadata.highest_severity_finding ?? "None";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <MetaCard label="Primary Language" value={metadata.primary_language} />
      <MetaCard label="Architecture Pattern" value={metadata.detected_architecture_pattern} />
      <MetaCard
        label="Architecture Confidence"
        value={metadata.architecture_confidence}
      />
      <MetaCard label="Files Analyzed" value={metadata.total_files_analyzed.toLocaleString()} />
      <MetaCard
        label="Analysis Duration"
        value={`${metadata.analysis_duration_seconds}s`}
      />
      <MetaCard
        label="Highest Severity"
        value={highestSeverity}
        valueClass={
          metadata.highest_severity_finding
            ? SEVERITY_COLORS[metadata.highest_severity_finding]
            : "text-gray-500"
        }
      />
      <div className="sm:col-span-2 lg:col-span-3 rounded-lg border border-gray-200 p-4 bg-white">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Security Findings by Severity
        </p>
        <div className="flex flex-wrap gap-2">
          {SEVERITY_ORDER.map((sev) => {
            const count = metadata.finding_counts_by_severity[sev] ?? 0;
            return (
              <span
                key={sev}
                className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs font-medium ${SEVERITY_COLORS[sev]}`}
              >
                {sev}: {count}
              </span>
            );
          })}
        </div>
      </div>
      <MetaCard label="Recommendations" value={metadata.recommendation_count.toLocaleString()} />
      <MetaCard label="P1 Recommendations" value={metadata.p1_recommendation_count.toLocaleString()} />
      <MetaCard label="RAG Chunks Used" value={metadata.rag_chunks_used_count.toLocaleString()} />
      <MetaCard label="LLM Tokens Used" value={metadata.total_llm_tokens_used.toLocaleString()} />
    </div>
  );
}

function MetaCard({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 bg-white">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-base font-medium ${valueClass ?? "text-gray-800"}`}>{value}</p>
    </div>
  );
}
