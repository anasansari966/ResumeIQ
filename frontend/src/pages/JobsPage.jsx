import { useEffect, useMemo, useRef, useState } from "react";
import { Upload } from "lucide-react";
import api from "../api";
import JobCard from "../components/JobCard";
import JobDetailsModal from "../components/JobDetailsModal";
import JobProcessingLoader from "../components/JobProcessingLoader";
import SkeletonCard from "../components/SkeletonCard";
import useJobs from "../hooks/useJobs";
import useResumes from "../hooks/useResumes";
import { useToast } from "../components/Toast";

const SOURCES = [
  { value: "", label: "All platforms" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "indeed", label: "Indeed" },
  { value: "glassdoor", label: "Glassdoor" },
  { value: "google", label: "Google Jobs" },
  { value: "zip_recruiter", label: "ZipRecruiter" },
  { value: "bayt", label: "Bayt" },
  { value: "bdjobs", label: "BDJobs" },
  { value: "serpapi_web", label: "Company career sites" },
];
const EXP_LEVELS = ["all", "fresher", "1-3yr", "3-5yr", "5yr+"];
const JOB_TYPES = ["all", "full-time", "part-time", "remote", "internship"];
const DATE_POSTED = ["all", "today", "week", "month"];

export default function JobsPage() {
  const { showToast } = useToast();
  const { jobs, loading, smartSearch, searchMeta, setJobs } = useJobs();
  const { fetchResumes } = useResumes();

  const [query, setQuery] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [source, setSource] = useState("");
  const [experienceLevel, setExperienceLevel] = useState("all");
  const [jobType, setJobType] = useState("all");
  const [datePosted, setDatePosted] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedJob, setSelectedJob] = useState(null);
  const [profileResumeId, setProfileResumeId] = useState("");
  const [resumeReady, setResumeReady] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState("");
  const fileInputRef = useRef(null);

  useEffect(() => {
    let active = true;
    const loadProfile = async () => {
      await fetchResumes();
      if (!active) return;
      setJobs([]);
      setResumeReady(true);
    };
    loadProfile();
    return () => {
      active = false;
    };
  }, [fetchResumes, setJobs, smartSearch]);

  const uploadAndAnalyzeResume = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    setUploadingResume(true);
    setUploadedFileName(file.name);
    setProfileResumeId("");
    setLocationFilter("");
    setJobs([]);
    setPage(1);

    try {
      const response = await api.post("/resumes/upload", formData, { timeout: 180000 });
      const uploadedResume = response.data;
      if (!uploadedResume?.id) throw new Error("Resume upload did not return an ID.");

      const resumeId = String(uploadedResume.id);
      setProfileResumeId(resumeId);
      showToast({
        type: "success",
        message: "Resume uploaded. Generating suitable roles and checking eligible jobs.",
      });
      await fetchResumes();
      setUploadingResume(false);
      await smartSearch({ resumeId });
    } catch (error) {
      const detail = error.response?.data?.detail || error.message || "Resume upload failed.";
      setUploadedFileName("");
      showToast({ type: "error", message: detail });
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const filteredJobs = useMemo(() => {
    let rows = [...jobs];

    rows = rows.filter((job) => job.is_eligible !== false);

    if (source) {
      rows = rows.filter((job) => String(job.source || "").toLowerCase() === source.toLowerCase());
    }

    if (locationFilter) {
      rows = rows.filter((job) => {
        const jobLocation = String(job.location || "").trim().toLowerCase();
        const remote = String(job.remote || "").trim().toLowerCase();
        if (locationFilter === "__remote__") return remote === "remote" || remote === "hybrid" || jobLocation.includes("remote");
        return jobLocation === locationFilter.toLowerCase();
      });
    }

    if (experienceLevel !== "all") {
      rows = rows.filter((job) => {
        const required = job.required_experience_years;
        if (required == null) return true;
        if (experienceLevel === "fresher") return required <= 1;
        if (experienceLevel === "1-3yr") return required >= 1 && required <= 3;
        if (experienceLevel === "3-5yr") return required >= 3 && required <= 5;
        return required >= 5;
      });
    }

    if (jobType !== "all") {
      rows = rows.filter((job) => {
        const remote = String(job.remote || "").toLowerCase();
        const type = String(job.job_type || "").toLowerCase();
        if (jobType === "remote") return remote === "remote" || remote === "hybrid";
        return type.includes(jobType) || String(job.description || "").toLowerCase().includes(jobType);
      });
    }

    if (datePosted !== "all") {
      const now = Date.now();
      const days = { today: 1, week: 7, month: 31 }[datePosted] || 31;
      rows = rows.filter((job) => {
        if (!job.posted_at) return true;
        const t = new Date(job.posted_at).getTime();
        if (Number.isNaN(t)) return true;
        return (now - t) / 86400000 <= days;
      });
    }

    return rows;
  }, [jobs, source, locationFilter, experienceLevel, jobType, datePosted]);

  const locationOptions = useMemo(() => {
    const unique = new Map();
    let hasRemote = false;
    jobs.forEach((job) => {
      const label = String(job.location || "").trim();
      if (label) unique.set(label.toLowerCase(), label);
      const remote = String(job.remote || "").toLowerCase();
      if (remote === "remote" || remote === "hybrid" || label.toLowerCase().includes("remote")) hasRemote = true;
    });
    const options = [...unique.values()].sort((a, b) => a.localeCompare(b));
    return hasRemote ? [{ value: "__remote__", label: "Remote / Hybrid" }, ...options.map((label) => ({ value: label.toLowerCase(), label }))] : options.map((label) => ({ value: label.toLowerCase(), label }));
  }, [jobs]);

  const perPage = 6;
  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / perPage));
  const pageItems = filteredJobs.slice((page - 1) * perPage, page * perPage);

  const runSearch = async () => {
    await smartSearch({
      resumeId: profileResumeId,
      query,
      location: "",
      workType: jobType === "remote" ? "remote" : "all",
      datePosted,
    });
    setPage(1);
  };

  const toggleSaved = (job) => {
    setJobs((prev) => prev.map((item) => (item.id === job.id ? { ...item, saved: !item.saved } : item)));
  };

  return (
    <>
      <div className="space-y-6">
        <section className="surface-card border-teal-100 bg-gradient-to-br from-white to-teal-50/50">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">Resume-first matching</p>
              <h2 className="mt-1 text-xl font-bold text-gray-900">AI finds roles you are qualified for</h2>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-gray-600">
                Upload your resume to generate suitable role titles. Each live job is then checked against your experience,
                skills, and career level before it appears here.
              </p>
            </div>

            <div className="flex w-full flex-col items-start gap-2 lg:w-auto lg:items-end">
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                onChange={uploadAndAnalyzeResume}
              />
              <button
                type="button"
                className="btn-primary inline-flex items-center gap-2 whitespace-nowrap"
                disabled={uploadingResume || loading}
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={17} />
                {uploadingResume ? "Uploading resume..." : loading ? "Analyzing resume..." : "Upload resume"}
              </button>
              {uploadedFileName ? (
                <p className="max-w-64 truncate text-xs font-medium text-gray-500">{uploadedFileName}</p>
              ) : null}
            </div>
          </div>

          {!resumeReady ? (
            <p className="mt-4 text-sm text-gray-500">Preparing resume analysis...</p>
          ) : !profileResumeId ? (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="font-semibold text-amber-900">Upload a resume to begin</p>
              <p className="mt-1 text-sm text-amber-700">
                AI will analyze the uploaded resume, generate suitable roles, and search only for jobs you qualify for.
              </p>
            </div>
          ) : (
            <>
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                {[
                  ["1", "Resume analyzed", searchMeta.experienceYears != null ? `Skills extracted · ~${searchMeta.experienceYears} years detected` : "Skills extracted"],
                  ["2", "Roles generated", `${searchMeta.suggestedRoles.length || 0} suitable roles identified`],
                  ["3", "Eligibility checked", `${jobs.length} qualified jobs retained`],
                ].map(([step, title, detail]) => (
                  <div key={step} className="rounded-xl border border-teal-100 bg-white/80 p-3">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">{step}</span>
                      <p className="text-sm font-semibold text-gray-900">{title}</p>
                    </div>
                    <p className="mt-2 text-xs text-gray-500">{detail}</p>
                  </div>
                ))}
              </div>

              {searchMeta.suggestedRoles.length ? (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Roles generated from your resume</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {searchMeta.suggestedRoles.map((role) => (
                      <button
                        key={role}
                        type="button"
                        className="rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-700 hover:bg-teal-100"
                        onClick={() => setQuery(role)}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {searchMeta.message ? <p className="mt-3 text-xs leading-5 text-gray-500">{searchMeta.message}</p> : null}
            </>
          )}
        </section>

        {uploadingResume || loading ? <JobProcessingLoader uploading={uploadingResume} /> : null}

        <section className="surface-card">
          <div className="grid gap-3 md:grid-cols-[1.2fr,1fr,auto]">
            <input
              className="input-base"
              placeholder="Search by role or keywords"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <select
              className="input-base"
              aria-label="Filter jobs by location"
              value={locationFilter}
              onChange={(event) => {
                setLocationFilter(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All locations</option>
              {locationOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <button type="button" className="btn-primary" disabled={!profileResumeId || loading} onClick={runSearch}>
              {loading ? "Searching..." : "Search eligible jobs"}
            </button>
          </div>
        </section>

        <div className="grid gap-4 lg:grid-cols-[280px,1fr]">
          <aside className="surface-card space-y-4">
            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Experience level</p>
              <div className="space-y-2 text-sm text-gray-600">
                {EXP_LEVELS.map((item) => (
                  <label key={item} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="exp"
                      checked={experienceLevel === item}
                      onChange={() => setExperienceLevel(item)}
                    />
                    {item}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Job type</p>
              <div className="space-y-2 text-sm text-gray-600">
                {JOB_TYPES.map((item) => (
                  <label key={item} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="jobtype"
                      checked={jobType === item}
                      onChange={() => setJobType(item)}
                    />
                    {item}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Source</p>
              <select className="input-base" value={source} onChange={(event) => setSource(event.target.value)}>
                {SOURCES.map((item) => (
                  <option key={item.value || "all"} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <p className="mb-2 text-sm font-semibold text-gray-900">Date posted</p>
              <select className="input-base" value={datePosted} onChange={(event) => setDatePosted(event.target.value)}>
                {DATE_POSTED.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
          </aside>

          <section>
            {loading ? (
              <SkeletonCard count={6} />
            ) : pageItems.length ? (
              <>
                <div className="grid gap-4 xl:grid-cols-2">
                  {pageItems.map((job) => (
                    <JobCard key={job.id} job={job} onSave={toggleSaved} onOpen={setSelectedJob} />
                  ))}
                </div>

                <div className="mt-6 flex items-center justify-center gap-2">
                  <button type="button" className="btn-secondary" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </button>
                  <span className="px-3 text-sm text-gray-600">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={page === totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </>
            ) : (
              <div className="surface-card text-center">
                <p className="text-base font-semibold text-gray-900">
                  {profileResumeId ? "No eligible jobs found" : "Upload a resume to start"}
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  {profileResumeId
                    ? locationFilter
                      ? "No eligible jobs match this location. Choose All locations to see every result instantly."
                      : "Try a generated role or a wider posting date. Jobs that fail skills, role, or experience checks are hidden."
                    : "Job recommendations require an uploaded resume so eligibility can be verified."}
                </p>
              </div>
            )}
          </section>
        </div>
      </div>

      {selectedJob ? <JobDetailsModal job={selectedJob} onClose={() => setSelectedJob(null)} /> : null}
    </>
  );
}
