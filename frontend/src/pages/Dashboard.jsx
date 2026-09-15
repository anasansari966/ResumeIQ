import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, UploadCloud } from "lucide-react";
import ResumeCard from "../components/ResumeCard";
import JobCard from "../components/JobCard";
import SkeletonCard from "../components/SkeletonCard";
import ConfirmModal from "../components/ConfirmModal";
import useAuth from "../hooks/useAuth";
import useResumes from "../hooks/useResumes";
import useJobs from "../hooks/useJobs";
import useApplications from "../hooks/useApplications";
import { useToast } from "../components/Toast";

function scoreTone(score) {
  if (score < 50) return "text-red-600";
  if (score <= 75) return "text-amber-600";
  return "text-emerald-600";
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();

  const { resumes, loading: resumesLoading, fetchResumes, deleteResume, duplicateResume, downloadResume } = useResumes();
  const { jobs, loading: jobsLoading, matchJobs, setJobs } = useJobs();
  const {
    applications,
    loading: applicationsLoading,
    fetchApplications,
    createApplication,
  } = useApplications();

  const [deleteTarget, setDeleteTarget] = useState(null);

  useEffect(() => {
    const load = async () => {
      await Promise.all([fetchResumes(), fetchApplications(), matchJobs()]);
    };
    load();
  }, [fetchResumes, fetchApplications, matchJobs]);

  const totalResumes = resumes.length;
  const applicationsSent = applications.length;
  const jobsSaved = applications.filter((item) => item.status === "saved").length;
  const avgAts = useMemo(() => {
    if (!resumes.length) return 0;
    const sum = resumes.reduce((acc, item) => acc + Number(item.ats_baseline || item.parsed_json?.ats_score_baseline || 0), 0);
    return Math.round(sum / resumes.length);
  }, [resumes]);

  const recommendedJobs = jobs.slice(0, 3);

  const handleDeleteResume = async () => {
    if (!deleteTarget) return;
    await deleteResume(deleteTarget.id);
    setDeleteTarget(null);
  };

  const handleApplyJob = async (job) => {
    const firstResume = resumes[0];
    if (!firstResume) {
      showToast({ type: "warning", message: "Create a resume before applying." });
      navigate("/resume/new");
      return;
    }
    try {
      await createApplication({
        job_id: job.id,
        resume_id: firstResume.id,
        status: "saved",
      });
      showToast({ type: "success", message: "Job saved to applications." });
    } catch {
      /* handled in hook */
    }
  };

  void applicationsLoading;

  return (
    <>
      <div className="space-y-6">
        <section className="relative overflow-hidden rounded-2xl border border-teal-800/20 bg-[#0b1324] p-6 text-white sm:p-8">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-teal-400/20 blur-3xl"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -bottom-24 left-1/3 h-48 w-48 rounded-full bg-sky-400/10 blur-3xl"
          />
          <p className="relative text-xs font-semibold uppercase tracking-[0.22em] text-teal-200/90">ResumeIQ</p>
          <h2 className="relative mt-3 font-display text-3xl font-bold tracking-tight">
            {greeting()}, {user?.name?.split(" ")[0] || "there"}
          </h2>
          <p className="relative mt-2 max-w-xl text-sm text-slate-300">
            Track applications, refine ATS scores, and keep every resume interview-ready from one workspace.
          </p>
          <div className="relative mt-6 flex flex-wrap gap-3">
            <button type="button" className="btn-primary gap-2" onClick={() => navigate("/resume/onboarding")}>
              <UploadCloud className="h-4 w-4" />
              Upload resume
            </button>
            <button
              type="button"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/10"
              onClick={() => navigate("/resume/new")}
            >
              <Plus className="h-4 w-4" />
              Create resume
            </button>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Total Resumes",
              value: totalResumes,
              hint: (
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                  <Link to="/resume/new" className="font-medium text-teal-700 hover:text-teal-800">
                    Create New
                  </Link>
                  <Link to="/resume/onboarding" className="font-medium text-teal-700 hover:text-teal-800">
                    Upload resume
                  </Link>
                </div>
              ),
            },
            {
              label: "Jobs Saved",
              value: jobsSaved,
              hint: <p className="mt-2 text-sm text-slate-500">Saved opportunities for follow-up.</p>,
            },
            {
              label: "Applications Sent",
              value: applicationsSent,
              hint: <p className="mt-2 text-sm text-slate-500">Across all tracked job applications.</p>,
            },
            {
              label: "Average ATS Score",
              value: `${avgAts}/100`,
              valueClass: scoreTone(avgAts),
              hint: <p className="mt-2 text-sm text-slate-500">Calculated from all active resumes.</p>,
            },
          ].map((stat) => (
            <div key={stat.label} className="surface-card">
              <p className="text-sm text-slate-500">{stat.label}</p>
              <p className={`mt-2 font-display text-3xl font-bold ${stat.valueClass || "text-slate-900"}`}>{stat.value}</p>
              {stat.hint}
            </div>
          ))}
        </section>

        <section>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="font-display text-lg font-semibold text-slate-900">Recent Resumes</h3>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn-primary gap-2 px-3 py-2 text-sm"
                onClick={() => navigate("/resume/onboarding")}
              >
                <UploadCloud className="h-4 w-4 shrink-0" />
                Upload resume
              </button>
              <button type="button" className="btn-secondary px-3 py-2 text-sm" onClick={() => navigate("/resume/new")}>
                Open builder
              </button>
            </div>
          </div>

          {resumesLoading ? (
            <SkeletonCard count={3} />
          ) : resumes.length ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {resumes.slice(0, 6).map((resume) => (
                <ResumeCard
                  key={resume.id}
                  resume={resume}
                  onEdit={() => navigate(`/resume/${resume.id}/edit`)}
                  onDownload={() => downloadResume(resume.id, "pdf", resume.active_template_id || "")}
                  onDuplicate={async () => {
                    await duplicateResume(resume);
                    await fetchResumes();
                  }}
                  onDelete={() => setDeleteTarget(resume)}
                />
              ))}
            </div>
          ) : (
            <div className="surface-card text-center">
              <p className="text-sm text-slate-600">
                No resumes yet. Upload a PDF or Word file to import yours, or start from scratch in the builder.
              </p>
              <div className="mt-5 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
                <button
                  type="button"
                  className="btn-primary inline-flex w-full items-center justify-center gap-2 sm:w-auto"
                  onClick={() => navigate("/resume/onboarding")}
                >
                  <UploadCloud className="h-4 w-4 shrink-0" />
                  Upload resume
                </button>
                <button
                  type="button"
                  className="btn-secondary inline-flex w-full items-center justify-center sm:w-auto"
                  onClick={() => navigate("/resume/new")}
                >
                  Open builder
                </button>
              </div>
            </div>
          )}
        </section>

        <section>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-display text-lg font-semibold text-slate-900">Job Recommendations</h3>
            <Link to="/jobs" className="text-sm font-medium text-teal-700 hover:text-teal-800">
              View all jobs
            </Link>
          </div>

          {jobsLoading ? (
            <SkeletonCard count={3} />
          ) : recommendedJobs.length ? (
            <div className="grid gap-4 xl:grid-cols-3">
              {recommendedJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onSave={(target) => {
                    setJobs((prev) => prev.map((item) => (item.id === target.id ? { ...item, saved: !item.saved } : item)));
                  }}
                  onApply={handleApplyJob}
                />
              ))}
            </div>
          ) : (
            <div className="surface-card text-center">
              <p className="text-sm text-slate-600">No recommendations yet. Run a job search to personalize results.</p>
            </div>
          )}
        </section>
      </div>

      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Delete Resume"
        message="This action cannot be undone. Do you want to delete this resume?"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDeleteResume}
        danger
        confirmText="Delete"
      />
    </>
  );
}
