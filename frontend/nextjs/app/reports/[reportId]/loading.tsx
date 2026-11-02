export default function ReportLoading() {
  return (
    <div className="flex flex-1 bg-[#0d1117]">
      {/* Sidebar skeleton */}
      <aside className="hidden lg:flex flex-col w-56 flex-shrink-0 border-r border-[#21262d] bg-[#0d1117]">
        <div className="px-4 py-4 border-b border-[#21262d]">
          <div className="h-3 bg-[#21262d] rounded w-32 animate-pulse" />
          <div className="h-2.5 bg-[#1c2128] rounded w-24 mt-2 animate-pulse" />
        </div>
        <div className="py-2 px-2 space-y-1">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-8 bg-[#1c2128] rounded-md animate-pulse" />
          ))}
        </div>
      </aside>

      {/* Content skeleton */}
      <div className="flex-1 min-w-0 px-5 lg:px-8 pb-20 space-y-8 pt-8">
        {/* Back link */}
        <div className="h-3 bg-[#21262d] rounded w-20 animate-pulse" />

        {/* Hero card */}
        <div className="rounded-xl border border-[#30363d] bg-[#161b22] overflow-hidden">
          <div className="h-0.5 bg-[#30363d]" />
          <div className="p-6 space-y-3">
            <div className="h-7 bg-[#21262d] rounded w-56 animate-pulse" />
            <div className="h-4 bg-[#1c2128] rounded w-80 animate-pulse" />
            <div className="flex gap-4 pt-1">
              <div className="h-3 bg-[#1c2128] rounded w-32 animate-pulse" />
              <div className="h-3 bg-[#1c2128] rounded w-24 animate-pulse" />
            </div>
          </div>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-[#30363d] bg-[#161b22] p-4 space-y-2">
              <div className="h-2.5 bg-[#21262d] rounded w-20 animate-pulse" />
              <div className="h-6 bg-[#21262d] rounded w-28 animate-pulse" />
              <div className="h-2.5 bg-[#1c2128] rounded w-16 animate-pulse" />
            </div>
          ))}
        </div>

        {/* Section skeletons */}
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="h-2.5 bg-[#21262d] rounded w-6 animate-pulse" />
              <div className="h-4 bg-[#21262d] rounded w-36 animate-pulse" />
              <div className="flex-1 h-px bg-[#21262d]" />
            </div>
            <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-5 space-y-2.5">
              <div className="h-3.5 bg-[#21262d] rounded animate-pulse" />
              <div className="h-3.5 bg-[#21262d] rounded w-5/6 animate-pulse" />
              <div className="h-3.5 bg-[#21262d] rounded w-4/6 animate-pulse" />
              <div className="h-3.5 bg-[#21262d] rounded w-3/4 animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
