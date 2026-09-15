import { BriefcaseBusiness, LoaderCircle, ScanSearch, Sparkles } from "lucide-react";

const steps = [
  [Sparkles, "Generating roles", "Matching skills and experience"],
  [BriefcaseBusiness, "Searching platforms", "Collecting current job listings"],
  [ScanSearch, "Checking eligibility", "Comparing each JD with your resume"],
];

export default function JobProcessingLoader({ uploading = false }) {
  return (
    <section
      className="overflow-hidden rounded-2xl border border-teal-100 bg-gradient-to-r from-teal-50 via-white to-cyan-50 p-5 shadow-sm"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col gap-5 md:flex-row md:items-center">
        <div className="flex shrink-0 items-center gap-3">
          <span className="relative flex h-12 w-12 items-center justify-center rounded-full bg-teal-700 text-white shadow-md shadow-teal-200">
            <span className="absolute inset-0 animate-ping rounded-full bg-teal-300 opacity-30" />
            <LoaderCircle className="relative h-6 w-6 animate-spin" />
          </span>
          <div>
            <p className="font-bold text-gray-900">{uploading ? "Uploading your resume" : "Finding eligible jobs"}</p>
            <p className="mt-0.5 text-xs text-gray-500">This can take a moment across multiple platforms.</p>
          </div>
        </div>

        <div className="grid flex-1 gap-2 sm:grid-cols-3">
          {steps.map(([Icon, title, detail], index) => (
            <div
              key={title}
              className="animate-pulse rounded-xl border border-white/80 bg-white/80 px-3 py-2.5"
              style={{ animationDelay: `${index * 220}ms` }}
            >
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-teal-600" />
                <p className="text-xs font-semibold text-gray-800">{title}</p>
              </div>
              <p className="mt-1 text-[11px] text-gray-500">{detail}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-teal-100">
        <div className="h-full w-2/3 animate-pulse rounded-full bg-gradient-to-r from-teal-500 to-cyan-400" />
      </div>
    </section>
  );
}
