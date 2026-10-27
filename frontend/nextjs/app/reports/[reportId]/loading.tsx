export default function ReportLoading() {
  return (
    <div className="py-8 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto flex gap-8">
        {/* Sidebar skeleton */}
        <div className="hidden lg:block w-44 flex-shrink-0">
          <div className="sticky top-6 space-y-2">
            <div className="h-2.5 bg-gray-200 rounded w-14 mb-4 animate-pulse" />
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-9 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        </div>

        {/* Content skeleton */}
        <div className="flex-1 min-w-0 space-y-8">
          {/* Back link placeholder */}
          <div className="h-4 bg-gray-100 rounded w-44 animate-pulse" />

          {/* Mobile nav skeleton */}
          <div className="lg:hidden flex gap-1.5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-7 w-20 bg-gray-100 rounded-full animate-pulse" />
            ))}
          </div>

          {/* Header */}
          <div className="space-y-2">
            <div className="h-8 bg-gray-200 rounded w-64 animate-pulse" />
            <div className="h-4 bg-gray-100 rounded w-52 animate-pulse" />
            <div className="h-4 bg-gray-100 rounded w-80 animate-pulse" />
          </div>

          {/* Metadata grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>

          {/* Section skeletons */}
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-3">
              <div className="h-6 bg-gray-200 rounded w-48 animate-pulse border-b border-gray-200 pb-2" />
              <div className="space-y-2">
                <div className="h-4 bg-gray-100 rounded animate-pulse" />
                <div className="h-4 bg-gray-100 rounded w-5/6 animate-pulse" />
                <div className="h-4 bg-gray-100 rounded w-4/6 animate-pulse" />
                <div className="h-4 bg-gray-100 rounded w-3/4 animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
