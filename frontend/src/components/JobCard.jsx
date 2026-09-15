import { CheckCircle2, Heart, MapPin } from "lucide-react";

const sourceTone = {
  linkedin: "bg-blue-100 text-blue-700",
  indeed: "bg-teal-100 text-teal-700",
  glassdoor: "bg-emerald-100 text-emerald-700",
  google: "bg-red-100 text-red-700",
  zip_recruiter: "bg-violet-100 text-violet-700",
  bayt: "bg-orange-100 text-orange-700",
  bdjobs: "bg-lime-100 text-lime-700",
  serpapi_web: "bg-cyan-100 text-cyan-700",
  naukri: "bg-amber-100 text-amber-700",
  adzuna: "bg-emerald-100 text-emerald-700",
};

const sourceLabels = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  glassdoor: "Glassdoor",
  google: "Google Jobs",
  zip_recruiter: "ZipRecruiter",
  bayt: "Bayt",
  bdjobs: "BDJobs",
  serpapi_web: "Career site",
};

export default function JobCard({ job, onSave, onOpen }) {
  const sourceKey = String(job?.source || "").toLowerCase();
  const sourceClass = sourceTone[sourceKey] || "bg-gray-100 text-gray-700";
  const sourceLabel = sourceLabels[sourceKey] || job?.source || "Source";
  const score = Number(job?.match_score || 0);
  const initials = String(job?.company || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();

  return (
    <article
      className="surface-card cursor-pointer transition hover:-translate-y-0.5 hover:shadow-md"
      role="button"
      tabIndex={0}
      aria-label={`View details for ${job?.title || "job"}`}
      onClick={() => onOpen?.(job)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen?.(job);
        }
      }}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-teal-100 text-xs font-semibold text-teal-700">
            {initials || "CO"}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">{job?.title || "Role"}</h3>
            <p className="text-sm text-gray-600">{job?.company || "Company"}</p>
            <p className="mt-1 flex items-center gap-1 text-xs text-gray-500">
              <MapPin className="h-3.5 w-3.5" />
              {job?.location || "Location not specified"}
            </p>
          </div>
        </div>

        <button
          type="button"
          aria-label={job?.saved ? "Remove saved job" : "Save job"}
          onClick={(event) => {
            event.stopPropagation();
            onSave?.(job);
          }}
          className={`rounded-full p-2 ${job?.saved ? "bg-red-50 text-red-500" : "bg-gray-100 text-gray-500 hover:bg-gray-200"}`}
        >
          <Heart className={`h-4 w-4 ${job?.saved ? "fill-current" : ""}`} />
        </button>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${sourceClass}`}>{sourceLabel}</span>
        {score ? <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">{Math.round(score)}% match</span> : null}
        {job?.is_eligible ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-teal-100 px-2.5 py-1 text-xs font-semibold text-teal-700">
            <CheckCircle2 className="h-3.5 w-3.5" /> Eligible
          </span>
        ) : null}
        {job?.salary_range ? (
          <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-700">{job.salary_range}</span>
        ) : null}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {(job?.skills || []).slice(0, 3).map((skill) => (
          <span key={skill} className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">
            {skill}
          </span>
        ))}
        {(job?.skills || []).length > 3 ? (
          <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">+{job.skills.length - 3} more</span>
        ) : null}
      </div>

      {job?.fit_rationale ? (
        <div className="mb-4 rounded-xl border border-teal-100 bg-teal-50/70 px-3 py-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-teal-700">Why you qualify</p>
          <p className="mt-1 text-xs leading-5 text-gray-600">{job.fit_rationale.replace(/^Eligible:\s*/i, "")}</p>
          {job?.candidate_experience_years != null ? (
            <p className="mt-1 text-[11px] text-gray-500">
              Resume: ~{job.candidate_experience_years} yr experience
              {job?.required_experience_years != null ? ` · Job asks: ${job.required_experience_years}+ yr` : ""}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">
          Posted {job?.posted_at ? new Date(job.posted_at).toLocaleDateString() : "recently"}
        </p>
        <button
          type="button"
          className="btn-primary"
          onClick={(event) => {
            event.stopPropagation();
            onOpen?.(job);
          }}
        >
          View job
        </button>
      </div>
    </article>
  );
}
