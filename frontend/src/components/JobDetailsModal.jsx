import { useEffect } from "react";
import { BriefcaseBusiness, CheckCircle2, ExternalLink, MapPin, X } from "lucide-react";

const sourceLabels = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  glassdoor: "Glassdoor",
  google: "Google Jobs",
  zip_recruiter: "ZipRecruiter",
  bayt: "Bayt",
  bdjobs: "BDJobs",
  serpapi_web: "Company career site",
};

function safeExternalUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

export default function JobDetailsModal({ job, onClose }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  if (!job) return null;

  const score = Math.max(0, Math.min(100, Math.round(Number(job.match_score || 0))));
  const applyUrl = safeExternalUrl(job.apply_url);
  const sourceLabel = sourceLabels[String(job.source || "").toLowerCase()] || job.source || "Job opportunity";
  const scoreTone = score >= 80 ? "bg-emerald-500" : score >= 60 ? "bg-teal-500" : "bg-amber-500";
  const scoreText = score >= 80 ? "Strong match" : score >= 60 ? "Good match" : "Possible match";
  const reasons = job.eligibility_reasons || [];
  const matchingSkills = job.matching_skills || [];
  const missingSkills = job.missing_skills || [];

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 sm:p-6" role="dialog" aria-modal="true">
      <button type="button" className="absolute inset-0 bg-gray-950/55" aria-label="Close job details" onClick={onClose} />

      <div className="relative z-10 flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-gray-200 px-5 py-5 sm:px-7">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-teal-700">
              <span>{sourceLabel}</span>
              {job.is_eligible ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-teal-50 px-2 py-1 normal-case tracking-normal">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Eligible
                </span>
              ) : null}
            </div>
            <h2 className="text-xl font-bold text-gray-950 sm:text-2xl">{job.title || "Job details"}</h2>
            <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-sm text-gray-600">
              <span className="inline-flex items-center gap-1.5"><BriefcaseBusiness className="h-4 w-4" />{job.company || "Company"}</span>
              <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4" />{job.location || "Location not specified"}</span>
            </div>
          </div>
          <button type="button" className="rounded-full bg-gray-100 p-2 text-gray-500 hover:bg-gray-200" aria-label="Close" onClick={onClose}>
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="grid min-h-0 flex-1 overflow-y-auto lg:grid-cols-[minmax(0,1fr),340px] lg:overflow-hidden">
          <main className="overflow-y-auto px-5 py-6 sm:px-7">
            <section>
              <h3 className="text-base font-bold text-gray-900">Job description</h3>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-600">
                {job.description || "A detailed description was not provided by this employer."}
              </p>
            </section>

            {job.skills?.length ? (
              <section className="mt-7 border-t border-gray-100 pt-6">
                <h3 className="text-base font-bold text-gray-900">Required skills</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {job.skills.map((skill) => (
                    <span key={skill} className="rounded-full bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-700">{skill}</span>
                  ))}
                </div>
              </section>
            ) : null}
          </main>

          <aside className="overflow-y-auto border-t border-gray-200 bg-gray-50/80 p-5 lg:border-l lg:border-t-0 sm:p-6">
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-500">Shortlist match</p>
              <div className="mt-3 flex items-end justify-between gap-4">
                <p className="text-4xl font-extrabold text-gray-950">{score}%</p>
                <p className="pb-1 text-sm font-semibold text-teal-700">{scoreText}</p>
              </div>
              <div className="mt-4 h-3 overflow-hidden rounded-full bg-gray-200" aria-label={`${score}% shortlist match`}>
                <div className={`h-full rounded-full ${scoreTone} transition-all`} style={{ width: `${score}%` }} />
              </div>
              <div className="mt-1.5 flex justify-between text-[10px] font-medium text-gray-400">
                <span>0</span><span>50</span><span>100</span>
              </div>
              <p className="mt-3 text-xs leading-5 text-gray-500">
                Based on generated-role alignment, resume skills, experience, and employer requirements.
              </p>
            </div>

            <div className="mt-4 rounded-2xl border border-teal-100 bg-teal-50/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">Why you qualify</p>
              <p className="mt-2 text-sm leading-6 text-gray-700">
                {(job.fit_rationale || "Your resume meets the main eligibility requirements.").replace(/^Eligible:\s*/i, "")}
              </p>
              {reasons.length ? (
                <ul className="mt-3 space-y-2">
                  {reasons.slice(0, 4).map((reason) => (
                    <li key={reason} className="flex gap-2 text-xs leading-5 text-gray-600">
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-600" />{reason}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>

            {matchingSkills.length ? (
              <div className="mt-4">
                <p className="text-xs font-semibold text-gray-700">Matching skills</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {matchingSkills.slice(0, 10).map((skill) => (
                    <span key={skill} className="rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-medium text-emerald-700">{skill}</span>
                  ))}
                </div>
              </div>
            ) : null}

            {missingSkills.length ? (
              <div className="mt-4">
                <p className="text-xs font-semibold text-gray-700">Skills to review</p>
                <p className="mt-1 text-xs leading-5 text-gray-500">{missingSkills.slice(0, 6).join(", ")}</p>
              </div>
            ) : null}

            <div className="mt-6">
              {applyUrl ? (
                <a href={applyUrl} target="_blank" rel="noopener noreferrer" className="btn-primary flex w-full items-center justify-center gap-2">
                  Apply now <ExternalLink className="h-4 w-4" />
                </a>
              ) : (
                <button type="button" className="btn-primary w-full opacity-60" disabled>Application link unavailable</button>
              )}
              <p className="mt-2 text-center text-[11px] text-gray-500">Opens the employer application page in a new tab.</p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
