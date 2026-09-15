export default function SkeletonCard({ count = 3, className = "" }) {
  return (
    <div className={`grid gap-4 sm:grid-cols-2 xl:grid-cols-3 ${className}`}>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="surface-card animate-pulse">
          <div className="mb-4 flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gray-200" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-2/3 rounded bg-gray-200" />
              <div className="h-2.5 w-1/2 rounded bg-gray-100" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="h-2.5 w-full rounded bg-gray-100" />
            <div className="h-2.5 w-5/6 rounded bg-gray-100" />
          </div>
        </div>
      ))}
    </div>
  );
}
