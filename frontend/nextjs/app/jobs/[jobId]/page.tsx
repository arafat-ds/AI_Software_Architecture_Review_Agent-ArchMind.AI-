import JobPoller from "@/components/JobPoller";

interface Props {
  params: Promise<{ jobId: string }>;
}

export default async function JobPage({ params }: Props) {
  const { jobId } = await params;

  return (
    <div className="max-w-lg mx-auto pt-16">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
        <JobPoller jobId={jobId} />
      </div>
    </div>
  );
}
