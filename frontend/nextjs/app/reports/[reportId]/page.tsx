import { notFound } from "next/navigation";
import ReportViewer from "@/components/ReportViewer";
import type { ReportResponse } from "@/types/archmind";
import { getBackendConfig } from "@/lib/server-config";

interface Props {
  params: Promise<{ reportId: string }>;
}

async function fetchReport(reportId: string): Promise<ReportResponse | null> {
  const { baseUrl, apiKey } = getBackendConfig();
  const res = await fetch(`${baseUrl}/api/v1/reports/${reportId}`, {
    headers: { "X-API-Key": apiKey },
    next: { revalidate: 0 },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

export default async function ReportPage({ params }: Props) {
  const { reportId } = await params;
  const report = await fetchReport(reportId);

  if (!report) notFound();

  return (
    <div className="py-8 px-4 sm:px-6">
      <ReportViewer report={report} />
    </div>
  );
}
