import JobPoller from "@/components/JobPoller";

interface Props {
  params: Promise<{ jobId: string }>;
}

export default async function JobPage({ params }: Props) {
  const { jobId } = await params;
  return <JobPoller jobId={jobId} />;
}
