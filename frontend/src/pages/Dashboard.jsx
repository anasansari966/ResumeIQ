import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { api, getToken } from "../api.js";
import DocxTemplatePreview from "../components/AnimatedResumePreview.jsx";
import TemplatePickerModal from "../components/TemplatePickerModal.jsx";
import WorkflowProgress from "../components/WorkflowProgress.jsx";
import { templateFileTitle } from "../templateDisplayName.js";
import ResumeStructureEditor from "../components/ResumeStructureEditor.jsx";
import TrackerAnalytics from "../components/TrackerAnalytics.jsx";
import { VISUALS } from "../theme/visuals.js";

const HUB_AI = "ai";
const HUB_CAREER = "career";

const AI_TABS = [
  { id: "enhance", label: "ATS enhancement" },
  { id: "tailor", label: "JD tailor" },
];

const CAREER_TABS = [
  { id: "resume", label: "Resume" },
  { id: "jobs", label: "Job search" },
  { id: "tracker", label: "Tracker" },
];

const ATS_ENHANCE_HINT = 70;

const TRACK_STAGES = ["saved", "applied", "phone_screen", "interview", "offer", "rejected", "archived"];

const TAILOR_JD_STORAGE_KEY = "resumeiq.tailor.jdDraft";
const JOB_COUNTRY_STORAGE_KEY = "resumeiq.jobs.country";
const JOB_WORK_TYPE_STORAGE_KEY = "resumeiq.jobs.workType";
const JOB_DATE_POSTED_STORAGE_KEY = "resumeiq.jobs.datePosted";

const TAB_ICON = {
  enhance: "✨",
  tailor: "🎯",
  resume: "📄",
  jobs: "🔎",
  tracker: "📋",
};

const COUNTRY_OPTIONS = [
  { code: "", label: "Global (all countries)" },
  { code: "us", label: "United States" },
  { code: "ca", label: "Canada" },
  { code: "gb", label: "United Kingdom" },
  { code: "au", label: "Australia" },
  { code: "de", label: "Germany" },
  { code: "fr", label: "France" },
  { code: "nl", label: "Netherlands" },
  { code: "se", label: "Sweden" },
  { code: "ch", label: "Switzerland" },
  { code: "ae", label: "United Arab Emirates" },
  { code: "sa", label: "Saudi Arabia" },
  { code: "in", label: "India" },
  { code: "sg", label: "Singapore" },
  { code: "jp", label: "Japan" },
  { code: "kr", label: "South Korea" },
  { code: "my", label: "Malaysia" },
  { code: "id", label: "Indonesia" },
  { code: "ph", label: "Philippines" },
  { code: "za", label: "South Africa" },
  { code: "br", label: "Brazil" },
  { code: "mx", label: "Mexico" },
];

function normalizeCountryCode(raw) {
  const val = (raw || "").trim().toLowerCase();
  if (!val) return "";
  if (COUNTRY_OPTIONS.some((c) => c.code === val)) return val;
  const byLabel = COUNTRY_OPTIONS.find((c) => c.label.toLowerCase() === val);
  return byLabel?.code || "";
}

/** Match datalist label to ISO code so Search works even if the input never fired blur. */
function resolveJobCountryCode(searchLabel, fallbackCode) {
  const t = (searchLabel || "").trim();
  if (!t || /^global/i.test(t) || t.toLowerCase() === "global (all countries)") return "";
  const hit = COUNTRY_OPTIONS.find((c) => c.label.toLowerCase() === t.toLowerCase());
  if (hit) return hit.code;
  return normalizeCountryCode(t) || fallbackCode || "";
}

/** Instant filters on cached job search results (no API round-trip). */
function jobMatchesWorkTypeClient(job, wtype) {
  if (!wtype || wtype === "all") return true;
  const rem = (job.remote || "").toLowerCase();
  const blob = `${job.title || ""} ${job.location || ""} ${(job.description || "").slice(0, 2800)}`.toLowerCase();
  if (wtype === "remote") {
    if (rem === "remote" || rem === "hybrid") return true;
    return ["remote", "work from home", "wfh", "work-from-home", "fully remote"].some((x) => blob.includes(x));
  }
  if (wtype === "on-site") {
    if (rem === "remote") {
      if (blob.includes("hybrid")) return true;
      return false;
    }
    return true;
  }
  return true;
}

function jobMatchesDatePostedClient(job, datePosted) {
  if (!datePosted || datePosted === "all") return true;
  const limDays = { today: 1, "3days": 3, week: 7, month: 31 }[datePosted];
  if (limDays == null) return true;
  if (!job.posted_at) return true;
  const t = new Date(job.posted_at).getTime();
  if (Number.isNaN(t)) return true;
  const days = (Date.now() - t) / 86400000;
  return days <= limDays + 0.5;
}

/** Advanced custom search: append API results without clearing resume-based matches (dedupe by id). */
function mergeJobSearchPools(prev, incoming) {
  const seen = new Set(prev.map((j) => j.id).filter((id) => id != null));
  const out = [...prev];
  for (const j of incoming) {
    if (j && j.id != null && !seen.has(j.id)) {
      seen.add(j.id);
      out.push(j);
    }
  }
  out.sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0));
  return out;
}

/** Prefer original upload filename; fall back to stable id for legacy rows. */
function resumeFileLabel(r) {
  if (!r) return "";
  const raw = (r.file_name || "").trim();
  if (raw) {
    const base = raw.replace(/^[\\/]+/, "").split(/[/\\]/).pop();
    return base || raw;
  }
  return `Resume #${r.id}`;
}

async function downloadPdf(sessionId, templateId) {
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  const token = getToken();
  const url = `${base}/api/v1/tailor/${sessionId}/pdf${templateId ? `?template_id=${encodeURIComponent(templateId)}` : ""}`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error("PDF download failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `resumeiq-${sessionId}.pdf`;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadResumeFile(resumeId, kind, templateId = "") {
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  const token = getToken();
  const path = kind === "pdf" ? "export-pdf" : "export-tex";
  const qp = templateId ? `?template_id=${encodeURIComponent(templateId)}` : "";
  const res = await fetch(`${base}/api/v1/resumes/${resumeId}/${path}${qp}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || "Download failed");
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = kind === "pdf" ? `resume-${resumeId}.pdf` : `resume-${resumeId}.tex`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const hubParam = (searchParams.get("hub") || "").trim().toLowerCase();
  const tabParam = searchParams.get("tab") || "";

  const inferredHubFromTab = AI_TABS.some((t) => t.id === tabParam)
    ? HUB_AI
    : CAREER_TABS.some((t) => t.id === tabParam)
      ? HUB_CAREER
      : null;

  const serviceChosen =
    hubParam === HUB_AI ||
    hubParam === HUB_CAREER ||
    (Boolean(tabParam) && inferredHubFromTab !== null);

  let hub;
  let tab;
  if (!serviceChosen) {
    hub = HUB_CAREER;
    tab = "resume";
  } else if (hubParam === HUB_AI || hubParam === HUB_CAREER) {
    hub = hubParam;
    if (hub === HUB_CAREER) {
      tab = CAREER_TABS.some((t) => t.id === tabParam) ? tabParam : "resume";
    } else {
      tab = AI_TABS.some((t) => t.id === tabParam) ? tabParam : "enhance";
    }
  } else {
    hub = inferredHubFromTab;
    if (hub === HUB_CAREER) {
      tab = CAREER_TABS.some((t) => t.id === tabParam) ? tabParam : "resume";
    } else {
      tab = AI_TABS.some((t) => t.id === tabParam) ? tabParam : "enhance";
    }
  }

  function setTab(next) {
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        let nextHub = hub;
        if (AI_TABS.some((t) => t.id === next)) nextHub = HUB_AI;
        if (CAREER_TABS.some((t) => t.id === next)) nextHub = HUB_CAREER;
        p.set("hub", nextHub);
        p.set("tab", next);
        return p;
      },
      { replace: true },
    );
  }

  function setHub(nextHub) {
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.set("hub", nextHub);
        p.set("tab", nextHub === HUB_AI ? "enhance" : "resume");
        return p;
      },
      { replace: true },
    );
  }

  function chooseService(nextHub) {
    setSearchParams(
      { hub: nextHub, tab: nextHub === HUB_AI ? "enhance" : "resume" },
      { replace: true },
    );
  }

  function backToServicePicker() {
    setSearchParams({}, { replace: true });
  }

  const [resumes, setResumes] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [jdText, setJdText] = useState(() => {
    try {
      return sessionStorage.getItem(TAILOR_JD_STORAGE_KEY) || "";
    } catch {
      return "";
    }
  });
  const [jdRow, setJdRow] = useState(null);
  const [jdLoading, setJdLoading] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templateId, setTemplateId] = useState("");
  const [previewTemplateId, setPreviewTemplateId] = useState("");
  const [tailorSession, setTailorSession] = useState(null);
  const [tailorLoading, setTailorLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  /** JobSpy multi-board results (Job search tab — never filled from /jobs/match). */
  const [jobScrapePool, setJobScrapePool] = useState([]);
  const jobScrapePoolRef = useRef([]);
  /** DB listings for tracker cards (job titles for saved applications). */
  const [trackerDbJobs, setTrackerDbJobs] = useState([]);

  const [jobQuery, setJobQuery] = useState("");
  const [jobCountry, setJobCountry] = useState(() => {
    try {
      return normalizeCountryCode(sessionStorage.getItem(JOB_COUNTRY_STORAGE_KEY) || "");
    } catch {
      return "";
    }
  });
  const [jobCountrySearch, setJobCountrySearch] = useState(() => {
    try {
      const code = normalizeCountryCode(sessionStorage.getItem(JOB_COUNTRY_STORAGE_KEY) || "");
      return COUNTRY_OPTIONS.find((c) => c.code === code)?.label || "Global (all countries)";
    } catch {
      return "Global (all countries)";
    }
  });
  const [jobWorkType, setJobWorkType] = useState(() => {
    try {
      const val = (sessionStorage.getItem(JOB_WORK_TYPE_STORAGE_KEY) || "all").trim().toLowerCase();
      return ["all", "remote", "on-site"].includes(val) ? val : "all";
    } catch {
      return "all";
    }
  });
  const [jobDatePosted, setJobDatePosted] = useState(() => {
    try {
      const val = (sessionStorage.getItem(JOB_DATE_POSTED_STORAGE_KEY) || "week").trim().toLowerCase();
      return ["all", "today", "3days", "week", "month"].includes(val) ? val : "week";
    } catch {
      return "week";
    }
  });

  useEffect(() => {
    jobScrapePoolRef.current = jobScrapePool;
  }, [jobScrapePool]);

  const jobsFiltered = useMemo(
    () =>
      jobScrapePool.filter(
        (j) => jobMatchesWorkTypeClient(j, jobWorkType) && jobMatchesDatePostedClient(j, jobDatePosted),
      ),
    [jobScrapePool, jobWorkType, jobDatePosted],
  );
  const [jobSearchMeta, setJobSearchMeta] = useState({
    queries: [],
    message: "",
    experienceYears: null,
    experiencePhrase: "",
    suggestedRoles: [],
  });
  const [jobsLoading, setJobsLoading] = useState(false);
  const jobQueryRef = useRef("");
  jobQueryRef.current = jobQuery;
  const [apps, setApps] = useState([]);
  const [jobDetail, setJobDetail] = useState(null);
  const [jobDescRefreshLoading, setJobDescRefreshLoading] = useState(false);
  const [postUploadChoice, setPostUploadChoice] = useState(null);
  const [resumeExportLoading, setResumeExportLoading] = useState("");
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [templateSaving, setTemplateSaving] = useState(false);

  const loadResumes = useCallback(async () => {
    const list = await api("/api/v1/resumes");
    setResumes(list);
    setSelectedResumeId((prev) => {
      let fromUrl = NaN;
      try {
        const raw = new URLSearchParams(window.location.search).get("resume");
        fromUrl = raw != null && raw !== "" ? Number(raw) : NaN;
      } catch {
        fromUrl = NaN;
      }
      const fromUrlOk = !Number.isNaN(fromUrl) && list.some((r) => r.id === fromUrl);
      if (fromUrlOk) return fromUrl;
      if (prev != null && list.some((r) => r.id === prev)) return prev;
      return list[0]?.id ?? null;
    });
  }, []);

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const t = await api("/api/v1/templates");
      const list = Array.isArray(t) ? t : [];
      setTemplates(list);
      return list;
    } catch {
      setTemplates([]);
      return [];
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  const refreshJobDetailDescription = useCallback(async () => {
    if (!jobDetail?.id || !jobDetail.apply_url) return;
    setJobDescRefreshLoading(true);
    try {
      const qs =
        selectedResumeId != null ? `?resume_id=${encodeURIComponent(String(selectedResumeId))}` : "";
      const updated = await api(`/api/v1/jobs/listing/${jobDetail.id}/refresh-description${qs}`, {
        method: "POST",
      });
      setJobScrapePool((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      setJobDetail(updated);
    } catch (e) {
      window.alert(e?.message || "Could not load description");
    } finally {
      setJobDescRefreshLoading(false);
    }
  }, [jobDetail, selectedResumeId]);

  const fetchJSearchJobs = useCallback(
    async (includeManualOverride) => {
      const merge = Boolean(includeManualOverride);
      if (merge && !jobQueryRef.current.trim()) {
        window.alert("Enter a job title or keywords to add to your current results.");
        return;
      }
      setJobsLoading(true);
      if (!merge) {
        setJobScrapePool([]);
        setJobDetail(null);
      }
      try {
        const countryForApi = resolveJobCountryCode(jobCountrySearch, jobCountry);
        setJobCountry(countryForApi);
        // Wide fetch (all work types + max age window) so Work type / Date posted filter instantly client-side.
        const data = await api("/api/v1/jobs/jsearch/smart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume_id: selectedResumeId || null,
            manual_query: merge ? jobQueryRef.current.trim() : "",
            country: countryForApi,
            work_type: "all",
            date_posted: "all",
            page: 1,
            num_pages: 1,
          }),
        });
        const next = data.jobs || [];
        const merged = merge ? mergeJobSearchPools(jobScrapePoolRef.current, next) : next;
        setJobScrapePool(merged);
        if (merge) {
          setJobSearchMeta((prev) => ({
            queries: [...(prev.queries || []), ...(data.queries_used || [])],
            message: [prev.message, data.message].filter(Boolean).join(" · ") || data.message || "",
            experienceYears: data.experience_years_used ?? prev.experienceYears,
            experiencePhrase: data.experience_phrase || prev.experiencePhrase || "",
            suggestedRoles:
              prev.suggestedRoles?.length && data.suggested_roles?.length
                ? [...new Set([...prev.suggestedRoles, ...data.suggested_roles])]
                : data.suggested_roles?.length
                  ? data.suggested_roles
                  : prev.suggestedRoles || [],
          }));
        } else {
          setJobSearchMeta({
            queries: data.queries_used || [],
            message: data.message || "",
            experienceYears: data.experience_years_used ?? null,
            experiencePhrase: data.experience_phrase || "",
            suggestedRoles: data.suggested_roles || [],
          });
        }
        const visible = merged.filter(
          (j) => jobMatchesWorkTypeClient(j, jobWorkType) && jobMatchesDatePostedClient(j, jobDatePosted),
        );
        setJobDetail((prev) => {
          if (merge && prev && merged.some((j) => j.id === prev.id)) return prev;
          if (visible.length) return visible[0];
          if (merged.length) return merged[0];
          return null;
        });
      } catch (e) {
        if (!merge) {
          setJobScrapePool([]);
          setJobSearchMeta({
            queries: [],
            message: e?.message || "Job search failed",
            experienceYears: null,
            experiencePhrase: "",
            suggestedRoles: [],
          });
        } else {
          setJobSearchMeta((prev) => ({
            ...prev,
            message: `${prev.message || ""} Additional search failed: ${e?.message || "error"}`.trim(),
          }));
        }
      } finally {
        setJobsLoading(false);
      }
    },
    [selectedResumeId, jobCountry, jobCountrySearch, jobWorkType, jobDatePosted],
  );

  async function runManualJobSearch() {
    await fetchJSearchJobs(true);
  }

  function onCountryInputChange(value) {
    setJobCountrySearch(value);
    const trimmed = value.trim();
    if (!trimmed) {
      setJobCountry("");
      return;
    }
    const exact = COUNTRY_OPTIONS.find((c) => c.label.toLowerCase() === trimmed.toLowerCase());
    if (exact) {
      setJobCountry(exact.code);
      return;
    }
    const code = normalizeCountryCode(trimmed);
    if (code) setJobCountry(code);
  }

  function onCountryInputBlur() {
    const code = normalizeCountryCode(jobCountrySearch);
    const normalized = COUNTRY_OPTIONS.find((c) => c.code === code) || COUNTRY_OPTIONS[0];
    setJobCountry(normalized.code);
    setJobCountrySearch(normalized.label);
  }

  const loadApps = useCallback(async () => {
    const list = await api("/api/v1/applications");
    setApps(list);
  }, []);

  useEffect(() => {
    loadResumes();
    loadTemplates();
  }, [loadResumes, loadTemplates]);

  /** Only normalize URL once a service is chosen. Missing `hub` means the two-card picker — do not auto-fill. */
  useEffect(() => {
    if (!serviceChosen) return;
    if (searchParams.get("hub")) return;
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.set("hub", hub);
        p.set("tab", tab);
        return p;
      },
      { replace: true },
    );
  }, [serviceChosen, hub, tab, searchParams, setSearchParams]);

  useEffect(() => {
    try {
      sessionStorage.setItem(TAILOR_JD_STORAGE_KEY, jdText);
    } catch {
      /* ignore quota / private mode */
    }
  }, [jdText]);

  useEffect(() => {
    try {
      sessionStorage.setItem(JOB_COUNTRY_STORAGE_KEY, jobCountry);
      sessionStorage.setItem(JOB_WORK_TYPE_STORAGE_KEY, jobWorkType);
      sessionStorage.setItem(JOB_DATE_POSTED_STORAGE_KEY, jobDatePosted);
    } catch {
      /* ignore storage failures */
    }
  }, [jobCountry, jobWorkType, jobDatePosted]);

  useEffect(() => {
    if (selectedResumeId == null) return;
    let params;
    try {
      params = new URLSearchParams(window.location.search);
    } catch {
      return;
    }
    if (params.get("resume") === String(selectedResumeId)) return;
    setSearchParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.set("resume", String(selectedResumeId));
        return p;
      },
      { replace: true },
    );
  }, [selectedResumeId, setSearchParams]);

  useEffect(() => {
    setPreviewTemplateId("");
  }, [selectedResumeId]);

  useEffect(() => {
    if (!templates.length) {
      setTemplateId("");
      return;
    }
    const activeFromResume = resumes.find((r) => r.id === selectedResumeId)?.active_template_id || "";
    if (activeFromResume && templates.some((t) => t.id === activeFromResume)) {
      if (templateId !== activeFromResume) setTemplateId(activeFromResume);
      return;
    }
    if (!templateId || !templates.some((t) => t.id === templateId)) {
      setTemplateId(templates[0].id);
    }
  }, [templates, templateId, resumes, selectedResumeId]);

  useEffect(() => {
    if (!templates.length) {
      if (previewTemplateId) setPreviewTemplateId("");
      return;
    }
    if (previewTemplateId && templates.some((t) => t.id === previewTemplateId)) return;
    if (templateId && templates.some((t) => t.id === templateId)) {
      setPreviewTemplateId(templateId);
      return;
    }
    setPreviewTemplateId(templates[0].id);
  }, [templates, templateId, previewTemplateId]);

  useEffect(() => {
    if (hub !== HUB_CAREER || tab !== "tracker") return;
    loadApps();
    const q = new URLSearchParams();
    if (selectedResumeId) q.set("resume_id", String(selectedResumeId));
    api(`/api/v1/jobs/match?${q}`)
      .then((list) => setTrackerDbJobs(Array.isArray(list) ? list : []))
      .catch(() => setTrackerDbJobs([]));
  }, [hub, tab, selectedResumeId, loadApps]);

  /** Opening Job search should never show tracker/DB listings; drop detail if it isn’t from the last scrape. */
  useEffect(() => {
    if (hub !== HUB_CAREER || tab !== "jobs") return;
    setJobDetail((prev) => {
      if (!prev) return null;
      return jobScrapePool.some((j) => j.id === prev.id) ? prev : null;
    });
  }, [hub, tab, jobScrapePool]);

  /** Keep selected job in sync when Work type / Date posted filters change. */
  useEffect(() => {
    if (hub !== HUB_CAREER || tab !== "jobs") return;
    setJobDetail((prev) => {
      if (!prev) return jobsFiltered[0] || null;
      if (jobsFiltered.some((j) => j.id === prev.id)) return prev;
      return jobsFiltered[0] || null;
    });
  }, [hub, tab, jobsFiltered]);

  const selectedResume = resumes.find((r) => r.id === selectedResumeId) || null;
  const effectiveTemplateId =
    previewTemplateId && templates.some((t) => t.id === previewTemplateId) ? previewTemplateId : templateId;
  const currentTemplate =
    templates.find((t) => t.id === effectiveTemplateId) || templates.find((t) => t.id === templateId) || null;
  const folderTemplates = useMemo(() => templates.filter((item) => item.source === "folder"), [templates]);
  const templateLibrary = folderTemplates.length ? folderTemplates : templates;
  const usingFolderTemplateLibrary = folderTemplates.length > 0;
  const templateLibrarySummary = usingFolderTemplateLibrary
    ? `${folderTemplates.length} template${folderTemplates.length === 1 ? "" : "s"} discovered in Templates/`
    : templates.length
      ? `${templates.length} template${templates.length === 1 ? "" : "s"} available`
      : "No templates discovered yet";
  const hasResume = Boolean(selectedResume);
  const hasActiveTemplate = Boolean(currentTemplate);

  const jobBoardRegionLabel = (() => {
    const code = resolveJobCountryCode(jobCountrySearch, jobCountry);
    if (!code) return "Worldwide";
    return COUNTRY_OPTIONS.find((c) => c.code === code)?.label || jobCountrySearch.trim() || "Worldwide";
  })();

  /** @param {"career-resume" | "ai-enhance" | "ai-tailor"} redirect */
  async function onUpload(e, redirect = "career-resume") {
    const input = e.target;
    const file = input.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    setUploading(true);
    try {
      const token = getToken();
      const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
      const res = await fetch(`${base}/api/v1/resumes/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      await loadResumes();
      const refreshedTemplates = await loadTemplates();
      const refreshedFolderTemplates = refreshedTemplates.filter((item) => item.source === "folder");
      const refreshedTemplateLibrary = refreshedFolderTemplates.length ? refreshedFolderTemplates : refreshedTemplates;
      const nextTemplateId =
        data.active_template_id && refreshedTemplates.some((t) => t.id === data.active_template_id)
          ? data.active_template_id
          : refreshedTemplateLibrary[0]?.id || refreshedTemplates[0]?.id || "";
      setSelectedResumeId(data.id);
      setTemplateId(nextTemplateId);
      setPreviewTemplateId(nextTemplateId);
      setTemplatePickerOpen(refreshedTemplateLibrary.length > 0);
      if (redirect === "career-resume") {
        setPostUploadChoice({
          id: data.id,
          ats: data.ats_baseline,
          templateId: nextTemplateId,
        });
        setSearchParams(
          (prev) => {
            const p = new URLSearchParams(prev);
            p.set("hub", HUB_CAREER);
            p.set("tab", "resume");
            p.set("resume", String(data.id));
            return p;
          },
          { replace: true },
        );
      } else {
        setPostUploadChoice({
          id: data.id,
          ats: data.ats_baseline,
          templateId: nextTemplateId,
        });
        const tab = redirect === "ai-tailor" ? "tailor" : "enhance";
        setSearchParams(
          (prev) => {
            const p = new URLSearchParams(prev);
            p.set("hub", HUB_AI);
            p.set("tab", tab);
            p.set("resume", String(data.id));
            return p;
          },
          { replace: true },
        );
      }
    } finally {
      setUploading(false);
      try {
        input.value = "";
      } catch {
        /* ignore */
      }
    }
  }

  async function saveTemplateSelection(nextTemplateId, resumeIdOverride = selectedResumeId) {
    if (!resumeIdOverride || !nextTemplateId) return;
    setTemplateSaving(true);
    try {
      const updated = await api(`/api/v1/resumes/${resumeIdOverride}/select-template`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_id: nextTemplateId }),
      });
      const activeTemplate = updated.active_template_id || nextTemplateId;
      setTemplateId(activeTemplate);
      setPreviewTemplateId(activeTemplate);
      await loadResumes();
      setSelectedResumeId(updated.id);
      setPostUploadChoice((prev) =>
        prev && prev.id === updated.id
          ? { ...prev, templateId: activeTemplate }
          : prev,
      );
      setTemplatePickerOpen(false);
    } catch (e) {
      window.alert(e?.message || "Could not save template selection");
    } finally {
      setTemplateSaving(false);
    }
  }

  async function analyzeJd() {
    if (!jdText.trim()) return;
    setJdLoading(true);
    try {
      const row = await api("/api/v1/jd/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_jd: jdText }),
      });
      setJdRow(row);
    } finally {
      setJdLoading(false);
    }
  }

  async function runTailor() {
    if (!selectedResumeId || !jdRow) return;
    setTailorLoading(true);
    try {
      const session = await api("/api/v1/tailor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_id: selectedResumeId,
          jd_analysis_id: jdRow.id,
          template_id: effectiveTemplateId,
        }),
      });
      setTailorSession(session);
    } finally {
      setTailorLoading(false);
    }
  }

  async function onDownloadPdf() {
    if (!tailorSession) return;
    setPdfLoading(true);
    try {
      await downloadPdf(tailorSession.id, effectiveTemplateId);
    } finally {
      setPdfLoading(false);
    }
  }

  async function saveJob(job, status = "saved") {
    await api("/api/v1/applications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: job.id, resume_id: selectedResumeId, status }),
    });
    await loadApps();
  }

  async function patchApp(id, status) {
    await api(`/api/v1/applications/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    await loadApps();
  }

  const jobsById = useMemo(() => {
    const m = {};
    for (const j of trackerDbJobs) {
      if (j?.id != null) m[j.id] = j;
    }
    for (const j of jobScrapePool) {
      if (j?.id != null) m[j.id] = j;
    }
    return m;
  }, [trackerDbJobs, jobScrapePool]);
  const selectedTemplateName = templateFileTitle(currentTemplate?.name || effectiveTemplateId || "-");
  const careerWorkflowSteps = [
    {
      key: "upload",
      number: 1,
      title: "Upload resume",
      description: hasResume
        ? `${resumeFileLabel(selectedResume)} is ready for the workflow.`
        : "Start with a PDF, DOCX, DOC, or TXT resume so we can extract structure and skills.",
      status: hasResume ? "complete" : "current",
    },
    {
      key: "template",
      number: 2,
      title: usingFolderTemplateLibrary ? "Choose from Templates/" : "Choose template",
      description: hasResume
        ? hasActiveTemplate
          ? `${selectedTemplateName} is active. ${templateLibrarySummary}.`
          : `Pick the layout you want before exporting, tailoring, or applying. ${templateLibrarySummary}.`
        : "Upload a resume first, then choose the resume design you want to use everywhere else.",
      status: !hasResume ? "locked" : hasActiveTemplate ? "complete" : "current",
    },
    {
      key: "polish",
      number: 3,
      title: "Polish and export",
      description: "Review extracted fields, run ATS enhancement, and export a polished PDF or TEX.",
      status: hasResume && hasActiveTemplate ? "current" : "locked",
    },
    {
      key: "apply",
      number: 4,
      title: "Search, tailor, and track",
      description: "Use the selected resume and template for JD tailoring, job search, and application tracking.",
      status: hasResume && hasActiveTemplate ? "pending" : "locked",
    },
  ];
  const enhanceWorkflowSteps = [
    {
      key: "resume",
      number: 1,
      title: "Resume uploaded",
      description: hasResume
        ? `${resumeFileLabel(selectedResume)} is active in Resume AI.`
        : "Upload a resume to unlock editing and export tools.",
      status: hasResume ? "complete" : "current",
    },
    {
      key: "layout",
      number: 2,
      title: usingFolderTemplateLibrary ? "Template selected from Templates/" : "Template selected",
      description: hasActiveTemplate
        ? `${selectedTemplateName} will be used for preview and exports.`
        : "Choose the visual style before you continue with editing or export.",
      status: !hasResume ? "locked" : hasActiveTemplate ? "complete" : "current",
    },
    {
      key: "edit",
      number: 3,
      title: "Edit structure",
      description: "Update contact info, summary, experience, education, and skills in one structured editor.",
      status: hasResume && hasActiveTemplate ? "current" : "locked",
    },
    {
      key: "export",
      number: 4,
      title: "Export or tailor",
      description: "Download the final PDF/TEX or continue into JD tailoring with the same selected template.",
      status: hasResume && hasActiveTemplate ? "pending" : "locked",
    },
  ];
  const tailorWorkflowSteps = [
    {
      key: "resume",
      number: 1,
      title: "Resume ready",
      description: hasResume
        ? `${resumeFileLabel(selectedResume)} is selected for tailoring.`
        : "Upload a resume before analyzing a job description.",
      status: hasResume ? "complete" : "current",
    },
    {
      key: "template",
      number: 2,
      title: usingFolderTemplateLibrary ? "Template chosen from Templates/" : "Template chosen",
      description: hasActiveTemplate
        ? `${selectedTemplateName} will be used when generating the tailored output.`
        : "Pick the final layout before creating the tailored document.",
      status: !hasResume ? "locked" : hasActiveTemplate ? "complete" : "current",
    },
    {
      key: "jd",
      number: 3,
      title: "Analyze the job description",
      description: "Paste the JD to extract must-have keywords and role expectations.",
      status: hasResume && hasActiveTemplate ? "current" : "locked",
    },
    {
      key: "tailor",
      number: 4,
      title: "Generate the tailored resume",
      description: "Produce a targeted version and download the final PDF using the selected template.",
      status: hasResume && hasActiveTemplate ? "pending" : "locked",
    },
  ];

  async function reSalvageResume() {
    if (!selectedResumeId) return;
    await api(`/api/v1/resumes/${selectedResumeId}/re-salvage`, { method: "POST" });
    await loadResumes();
  }

  async function deleteResume(resumeId, e) {
    e?.stopPropagation?.();
    const victim = resumes.find((x) => x.id === resumeId);
    const victimLabel = victim ? resumeFileLabel(victim) : `resume #${resumeId}`;
    if (!window.confirm(`Delete “${victimLabel}”? This cannot be undone.`)) return;
    await api(`/api/v1/resumes/${resumeId}`, { method: "DELETE" });
    await loadResumes();
    setTailorSession(null);
    setPostUploadChoice((prev) => (prev?.id === resumeId ? null : prev));
  }

  async function onResumeExport(kind) {
    if (!selectedResumeId) return;
    setResumeExportLoading(kind);
    try {
      await downloadResumeFile(selectedResumeId, kind, effectiveTemplateId);
    } catch (e) {
      window.alert(e?.message || "Export failed");
    } finally {
      setResumeExportLoading("");
    }
  }

  const postBannerAts = postUploadChoice?.ats != null ? Math.round(postUploadChoice.ats) : null;
  const highlightEnhance = postBannerAts != null && postBannerAts < ATS_ENHANCE_HINT;

  const subTabs = hub === HUB_AI ? AI_TABS : CAREER_TABS;
  const hubLabel = hub === HUB_AI ? "Resume AI" : "Career";
  const pageTitle = useMemo(() => {
    const t = subTabs.find((x) => x.id === tab);
    return t?.label ?? "Workspace";
  }, [subTabs, tab]);

  function goTab(next) {
    setTab(next);
    setMobileNavOpen(false);
  }

  if (!serviceChosen) {
    return (
      <div className="relative min-h-screen overflow-hidden bg-[#060912]">
        <div className="pointer-events-none fixed inset-0 z-0">
          <img
            src={VISUALS.servicePickerBg}
            alt=""
            className="h-full w-full object-cover opacity-[0.32] animate-bg-drift motion-reduce:scale-105 motion-reduce:animate-none"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-slate-950/88 to-indigo-950/95" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_90%_70%_at_30%_-15%,rgba(99,102,241,0.2),transparent_50%)]" />
          <div className="absolute bottom-0 left-1/2 h-96 w-[120%] -translate-x-1/2 bg-gradient-to-t from-cyan-500/10 to-transparent blur-3xl" />
        </div>

        <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 py-20">
          <div className="mb-12 max-w-lg animate-fade-in-scale text-center motion-reduce:animate-none">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-cyan-400/90">ResumeIQ</p>
            <h1 className="font-display mt-4 text-3xl font-bold tracking-tight text-white sm:text-4xl md:text-5xl">
              Where do you want to start?
            </h1>
            <p className="mt-3 text-sm text-slate-400 sm:text-base">Pick a workspace — you can switch any time.</p>
          </div>

          <div className="grid w-full max-w-md gap-8 sm:max-w-3xl sm:grid-cols-2 sm:gap-10">
            <button
              type="button"
              onClick={() => chooseService(HUB_AI)}
              className="group animate-stagger-1 relative overflow-hidden rounded-3xl border border-cyan-500/30 bg-slate-950/40 text-left shadow-2xl shadow-cyan-950/30 backdrop-blur-md transition duration-300 hover:border-cyan-400/55 hover:shadow-cyan-500/20 motion-reduce:animate-none"
            >
              <div className="service-card-media">
                <img src={VISUALS.cardResumeAi} alt="" loading="lazy" className="opacity-95" />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />
              </div>
              <div className="flex flex-col gap-2 px-7 py-7">
                <span className="inline-flex w-fit items-center gap-2 rounded-full border border-cyan-500/25 bg-cyan-950/40 px-3 py-1 text-xs font-medium text-cyan-200">
                  <span aria-hidden>✨</span> Polish & tailor
                </span>
                <span className="font-display text-2xl font-bold text-white">Resume AI</span>
                <span className="text-sm leading-relaxed text-slate-400">
                  ATS enhancement, structure edits, and JD-specific tailoring.
                </span>
              </div>
            </button>
            <button
              type="button"
              onClick={() => chooseService(HUB_CAREER)}
              className="group animate-stagger-2 relative overflow-hidden rounded-3xl border border-violet-500/30 bg-slate-950/40 text-left shadow-2xl shadow-violet-950/30 backdrop-blur-md transition duration-300 hover:border-violet-400/55 hover:shadow-violet-500/15 motion-reduce:animate-none"
            >
              <div className="service-card-media">
                <img src={VISUALS.cardCareer} alt="" loading="lazy" className="opacity-95" />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent" />
              </div>
              <div className="flex flex-col gap-2 px-7 py-7">
                <span className="inline-flex w-fit items-center gap-2 rounded-full border border-violet-500/25 bg-violet-950/40 px-3 py-1 text-xs font-medium text-violet-200">
                  <span aria-hidden>💼</span> Apply & track
                </span>
                <span className="font-display text-2xl font-bold text-white">Career</span>
                <span className="text-sm leading-relaxed text-slate-400">
                  Upload resumes, search roles, and manage your pipeline.
                </span>
              </div>
            </button>
          </div>

          <button
            type="button"
            onClick={logout}
            className="animate-stagger-3 fixed bottom-8 right-8 rounded-full border border-white/10 bg-slate-950/60 px-5 py-2.5 text-xs font-medium text-slate-400 shadow-lg backdrop-blur-md transition hover:border-white/20 hover:text-white motion-reduce:animate-none"
          >
            Sign out
          </button>
        </div>
      </div>
    );
  }

  const sidebarFlyout =
    "min-w-0 overflow-hidden transition-all duration-200 ease-out max-lg:max-w-none max-lg:opacity-100 lg:max-w-0 lg:opacity-0 lg:group-hover/side:max-w-[min(240px,55vw)] lg:group-hover/side:opacity-100";

  const sidebar = (
    <>
      <div className="flex h-14 shrink-0 items-center justify-end border-b border-white/10 px-4 lg:hidden">
        <button
          type="button"
          className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white"
          onClick={() => setMobileNavOpen(false)}
          aria-label="Close navigation"
        >
          ✕
        </button>
      </div>

      <div className="hidden h-14 shrink-0 items-center justify-center border-b border-white/10 lg:flex lg:group-hover/side:hidden">
        <span className="text-xl leading-none" aria-hidden title={hubLabel}>
          {hub === HUB_AI ? "✨" : "💼"}
        </span>
      </div>

      <div className="block border-b border-white/10 px-4 pb-4 pt-3 max-lg:block lg:hidden lg:group-hover/side:block lg:px-3 lg:pt-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-400/90">ResumeIQ</p>
        <p className="font-display mt-1 text-sm font-semibold text-white">{hubLabel}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">Hover to expand · Does not shift the page.</p>
      </div>

      <nav className="mt-3 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-3 pb-3" aria-label="Section">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 max-lg:opacity-100 lg:max-h-0 lg:overflow-hidden lg:opacity-0 lg:group-hover/side:mb-2 lg:group-hover/side:max-h-8 lg:group-hover/side:opacity-100">
          Sections
        </p>
        {subTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => goTab(t.id)}
            className={`sidebar-nav-item !items-center max-lg:!items-center lg:justify-center lg:gap-0 lg:px-2 lg:group-hover/side:justify-start lg:group-hover/side:gap-3 lg:group-hover/side:px-3 ${tab === t.id ? "sidebar-nav-active" : "sidebar-nav-idle"}`}
          >
            <span className="shrink-0 text-base leading-none" aria-hidden>
              {TAB_ICON[t.id] ?? "·"}
            </span>
            <span className={`truncate whitespace-nowrap ${sidebarFlyout}`}>{t.label}</span>
          </button>
        ))}
      </nav>

      <div className="mt-auto shrink-0 space-y-2 border-t border-white/10 p-3">
        <button
          type="button"
          onClick={backToServicePicker}
          title="Switch service"
          className="hidden w-full items-center justify-center rounded-lg py-2 text-sm text-slate-400 hover:bg-white/5 hover:text-cyan-300 max-lg:!hidden lg:flex lg:group-hover/side:hidden"
        >
          ⇄
        </button>
        <div className="flex min-w-0 items-center gap-2 lg:justify-center lg:group-hover/side:justify-start">
          <span
            className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/5 text-xs font-bold text-cyan-200 max-lg:!hidden lg:flex lg:group-hover/side:hidden"
            title={user?.email}
          >
            {(user?.email && user?.email[0]?.toUpperCase()) || "?"}
          </span>
          <p
            className={`flex-1 truncate text-[11px] text-slate-500 max-lg:block lg:hidden lg:group-hover/side:block`}
            title={user?.email}
          >
            {user?.email}
          </p>
        </div>
        <button
          type="button"
          onClick={backToServicePicker}
          className="hidden w-full py-1.5 text-center text-[11px] text-slate-500 hover:text-cyan-300 max-lg:block lg:group-hover/side:block"
        >
          Switch service
        </button>
        <button type="button" onClick={logout} className="ghost-btn w-full justify-center !py-2 text-xs">
          Sign out
        </button>
      </div>
    </>
  );

  return (
    <div
      className="app-bg app-bg--photo-mesh relative min-h-screen"
      style={{ "--mesh-photo": `url(${VISUALS.workspaceMesh})` }}
    >
      <TemplatePickerModal
        open={templatePickerOpen}
        templates={templateLibrary}
        selectedTemplateId={templateId}
        activePreviewTemplateId={effectiveTemplateId}
        resume={selectedResume}
        saving={templateSaving}
        onClose={() => setTemplatePickerOpen(false)}
        onPreviewChange={(nextTemplateId) => setPreviewTemplateId(nextTemplateId)}
        onSelect={saveTemplateSelection}
      />
      {mobileNavOpen && (
        <button
          type="button"
          className="fixed inset-0 z-[60] bg-black/55 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMobileNavOpen(false)}
          aria-label="Close menu"
        />
      )}

      <aside
        id="dashboard-sidebar"
        className={`group/side fixed inset-y-0 left-0 z-[70] flex min-h-0 flex-col border-r border-white/10 bg-slate-950/95 shadow-2xl shadow-black/50 backdrop-blur-xl transition-[transform,width] duration-200 ease-out max-lg:w-[min(288px,88vw)] lg:w-14 lg:overflow-x-hidden lg:overflow-y-auto lg:shadow-2xl lg:hover:w-72 ${
          mobileNavOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {sidebar}
      </aside>

      <div className="flex min-h-screen w-full min-w-0 flex-col lg:pl-14">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-white/10 bg-slate-950/80 px-3 py-2.5 backdrop-blur-xl lg:hidden">
          <button
            type="button"
            className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-white/10"
            onClick={() => setMobileNavOpen(true)}
            aria-expanded={mobileNavOpen}
            aria-controls="dashboard-sidebar"
          >
            Menu
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[10px] font-semibold uppercase tracking-wider text-cyan-400/80">{hubLabel}</p>
            <p className="truncate font-display text-sm font-semibold text-white">{pageTitle}</p>
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 pb-20 sm:px-6 sm:py-8 sm:pb-12">
          <div className="mb-6 hidden border-b border-white/5 pb-5 lg:block">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-400/80">{hubLabel}</p>
            <h2 className="font-display mt-1 text-2xl font-bold tracking-tight text-white">{pageTitle}</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">
              {hub === HUB_AI
                ? "Tune your resume for ATS and tailor it to a job description."
                : "Manage resumes, discover roles, and track applications in one place."}
            </p>
          </div>
        {hub === HUB_CAREER && tab === "resume" && (
          <section className="space-y-6">
            <WorkflowProgress
              eyebrow="Professional flow"
              title="Upload the resume first, choose a template next, then continue through the rest of the workspace"
              description="This keeps the experience structured for users: upload, select a design from the Templates folder library, then move into ATS improvement, tailoring, job search, and tracking."
              steps={careerWorkflowSteps}
            />
            {postUploadChoice && (
              <div
                className={`rounded-2xl border p-5 shadow-lg ${
                  highlightEnhance
                    ? "border-amber-500/50 bg-amber-950/30 ring-1 ring-amber-400/30"
                    : "border-white/10 bg-slate-900/40"
                }`}
              >
                <p className="text-sm font-semibold text-white">Resume uploaded successfully</p>
                <p className="mt-1 text-sm text-slate-300">
                  Baseline ATS score:{" "}
                  <span className="font-bold text-cyan-400">{postBannerAts != null ? `${postBannerAts}%` : "-"}</span>
                  {highlightEnhance && (
                    <span className="text-amber-200/90"> — consider ATS enhancement in Resume AI before applying.</span>
                  )}
                </p>
                <p className="mt-2 text-sm text-slate-400">
                  Next step: choose the resume template you want to use for previews, exports, and tailoring.
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedResumeId(postUploadChoice.id);
                      setTemplatePickerOpen(true);
                    }}
                    className="primary-btn px-4 py-2.5"
                  >
                    Choose template
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedResumeId(postUploadChoice.id);
                      goTab("enhance");
                    }}
                    className={`px-4 py-2.5 rounded-xl text-sm font-semibold transition ${
                      highlightEnhance
                        ? "bg-amber-500 text-slate-950 hover:bg-amber-400 shadow-md"
                        : "ghost-btn"
                    }`}
                  >
                    Open ATS enhancement
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedResumeId(postUploadChoice.id);
                      goTab("jobs");
                      setPostUploadChoice(null);
                    }}
                    className="ghost-btn px-4 py-2.5"
                  >
                    Continue to job search
                  </button>
                  <button
                    type="button"
                    onClick={() => setPostUploadChoice(null)}
                    className="px-3 py-2.5 text-sm text-slate-400 hover:text-white"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}
            <p className="max-w-2xl text-sm text-slate-400">
              Follow the workflow in order: upload the source resume, pick the final template from the library, then continue
              with editing, tailoring, job search, and tracking.
            </p>

            <div className="panel p-6 border border-violet-500/20 bg-violet-950/10">
              <h2 className="text-base font-semibold text-white">1 - Upload resume</h2>
              <p className="text-sm text-slate-400 mt-1">
                Start with the source resume. We extract contact details, experience, education, and skills so the rest of the
                workflow stays organized.
              </p>
              <label className="mt-4 inline-flex items-center gap-2 px-5 py-3 rounded-xl primary-btn cursor-pointer text-sm font-semibold">
                <input
                  type="file"
                  accept=".pdf,.docx,.doc,.txt"
                  className="hidden"
                  onChange={(e) => onUpload(e, "career-resume")}
                  disabled={uploading}
                />
                {uploading ? "Uploading..." : "Choose file to upload"}
              </label>
            </div>

            <div className="panel p-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-base font-semibold text-white">3 - Resume library</h2>
                {selectedResumeId && (
                  <button
                    type="button"
                    onClick={reSalvageResume}
                    className="text-xs font-medium text-cyan-300 border border-cyan-500/30 rounded-xl px-3 py-1.5 hover:bg-cyan-950/50"
                  >
                    Repair extraction
                  </button>
                )}
              </div>
              {resumes.length === 0 ? (
                <p className="text-sm text-slate-500 mt-2">No resumes yet.</p>
              ) : (
                <ul className="mt-3 divide-y divide-white/10">
                  {resumes.map((r) => (
                    <li key={r.id} className="py-3 flex justify-between items-center gap-3">
                      <button
                        type="button"
                        className={`flex-1 min-w-0 text-left text-sm ${selectedResumeId === r.id ? "font-semibold text-cyan-300" : "text-slate-200"}`}
                        onClick={() => setSelectedResumeId(r.id)}
                      >
                        {resumeFileLabel(r)}
                        <span className="block text-xs text-slate-500 font-normal">
                          Baseline ATS: {r.ats_baseline != null ? Math.round(r.ats_baseline) : "-"}
                        </span>
                        <span className="block text-[11px] text-slate-500 font-normal">
                          Template:{" "}
                          {templateFileTitle(
                            templates.find((t) => t.id === r.active_template_id)?.name || r.active_template_id || "Not set",
                          )}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={(e) => deleteResume(r.id, e)}
                        className="shrink-0 text-xs font-medium text-red-300 border border-red-500/30 rounded-xl px-2.5 py-1.5 hover:bg-red-950/40"
                      >
                        Delete
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="panel p-6 border border-cyan-500/20 bg-cyan-950/10">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="text-base font-semibold text-white">2 - Choose template</h2>
                  <p className="mt-1 max-w-2xl text-sm text-slate-400">
                    Once the resume is uploaded, choose the design before moving into ATS enhancement, tailoring, or export.
                  </p>
                  <p className="mt-2 text-xs text-slate-500">
                    {usingFolderTemplateLibrary
                      ? `${templateLibrarySummary}. This step is powered by the Templates/ folders in the project.`
                      : templateLibrarySummary}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setTemplatePickerOpen(true)}
                  disabled={!hasResume || !templateLibrary.length}
                  className="ghost-btn shrink-0 px-4 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {hasResume ? "Open template library" : "Upload a resume first"}
                </button>
              </div>

              {!hasResume ? (
                <div className="mt-5 rounded-2xl border border-dashed border-white/10 bg-black/20 px-4 py-8 text-center text-sm text-slate-500">
                  Upload a resume first, then choose a template from the library.
                </div>
              ) : templatesLoading ? (
                <p className="mt-4 text-sm text-slate-500">Loading templates...</p>
              ) : currentTemplate ? (
                <div className="mt-5 space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-cyan-500/25 bg-cyan-950/40 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
                      {(currentTemplate.kind || "template").replace(/_/g, " ")}
                    </span>
                    {currentTemplate.source === "folder" ? (
                      <span className="rounded-full border border-emerald-500/25 bg-emerald-950/35 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
                        Templates folder
                      </span>
                    ) : null}
                    <span className="text-sm font-semibold text-white">{selectedTemplateName}</span>
                    <span className="text-xs text-slate-500">{currentTemplate.best_for}</span>
                  </div>
                  <div className="rounded-[24px] border border-white/10 bg-slate-950/40 p-3 shadow-xl shadow-black/25">
                    <DocxTemplatePreview
                      template={currentTemplate}
                      templateId={currentTemplate.id}
                      resume={selectedResume}
                      className="min-h-[420px] rounded-[18px] border-white/5 bg-white"
                    />
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-slate-500">No templates were discovered yet.</p>
              )}
            </div>

            {selectedResume && (
              <details className="panel p-6 group">
                <summary className="text-base font-semibold text-white cursor-pointer list-none flex items-center justify-between">
                  Raw parsed JSON
                  <span className="text-xs font-normal text-slate-500">Advanced</span>
                </summary>
                <pre className="mt-3 text-xs bg-black/40 text-slate-200 p-4 rounded-xl overflow-auto max-h-96 border border-white/10">
                  {JSON.stringify(selectedResume.parsed_json, null, 2)}
                </pre>
              </details>
            )}

            <div className="flex flex-wrap justify-end gap-3 pt-2">
              <button
                type="button"
                disabled={!hasResume}
                onClick={() => goTab("enhance")}
                className="primary-btn px-6 py-2.5 disabled:cursor-not-allowed disabled:opacity-45"
              >
                Continue to ATS enhancement
              </button>
              <button
                type="button"
                disabled={!hasResume || !hasActiveTemplate}
                onClick={() => goTab("tailor")}
                className="ghost-btn px-4 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-45"
              >
                Continue to JD tailor
              </button>
              <button
                type="button"
                disabled={!hasResume}
                onClick={() => goTab("jobs")}
                className="ghost-btn px-4 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-45"
              >
                Go to job search
              </button>
            </div>
          </section>
        )}

        {hub === HUB_AI && tab === "enhance" && (
          <section className="space-y-6">
            <WorkflowProgress
              eyebrow="Resume AI flow"
              title="Upload, confirm the template, edit the structure, then export or tailor"
              description="Resume AI now follows the same guided order as the Career workspace so users always know the next professional step."
              steps={enhanceWorkflowSteps}
            />
            {resumes.length === 0 ? (
              <div className="mx-auto max-w-lg animate-fade-in-up">
                <div className="panel panel-interactive overflow-hidden p-6 sm:p-8">
                  <div className="animate-stagger-1 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 animate-float items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500/25 to-indigo-600/30 text-3xl shadow-lg shadow-cyan-900/30">
                      📄
                    </div>
                    <p className="text-lg font-semibold text-white">Upload a resume to begin</p>
                    <p className="mt-2 text-sm leading-relaxed text-slate-400 sm:text-base">
                      We&apos;ll parse it so you can improve keywords, structure, and export a polished PDF.
                    </p>
                  </div>
                  <label className="upload-dropzone mx-auto mt-8 block max-w-md cursor-pointer animate-stagger-2">
                    <input
                      type="file"
                      accept=".pdf,.docx,.doc,.txt"
                      className="sr-only"
                      onChange={(e) => onUpload(e, "ai-enhance")}
                      disabled={uploading}
                    />
                    <span className="pointer-events-none flex flex-col items-center gap-2">
                      <span className="font-display text-base font-semibold text-white">
                        {uploading ? "Uploading…" : "Upload resume"}
                      </span>
                      <span className="text-xs text-slate-500">PDF, DOCX, or TXT · tap to choose a file</span>
                    </span>
                  </label>
                  <p className="animate-stagger-3 mt-6 text-center text-xs text-slate-500">
                    Prefer managing files in Career?{" "}
                    <button
                      type="button"
                      className="font-medium text-cyan-400 underline decoration-cyan-500/40 underline-offset-2 hover:text-cyan-300"
                      onClick={() => goTab("resume")}
                    >
                      Open Career upload
                    </button>
                  </p>
                </div>
              </div>
            ) : (
              <div className="animate-fade-in-up space-y-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
                  <div>
                    <p className="max-w-xl text-sm text-slate-400">
                      Edit fields, confirm the selected template, then download PDF or TEX.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <label className="ghost-btn cursor-pointer !py-2 text-xs sm:text-sm">
                      <input
                        type="file"
                        accept=".pdf,.docx,.doc,.txt"
                        className="hidden"
                        onChange={(e) => onUpload(e, "ai-enhance")}
                        disabled={uploading}
                      />
                      {uploading ? "Uploading…" : "Replace resume"}
                    </label>
                    <button
                      type="button"
                      onClick={() => goTab("resume")}
                      className="ghost-btn !py-2 text-xs sm:text-sm"
                    >
                      Career hub
                    </button>
                  </div>
                </div>

                <div className="panel panel-interactive space-y-3 p-4 sm:p-5">
                  <div className="flex flex-wrap items-center gap-2 justify-between">
                    <p className="text-sm text-slate-300">
                      Template: <span className="font-semibold text-white">{selectedTemplateName}</span>
                    </p>
                    <span className="text-xs text-slate-500">
                      {usingFolderTemplateLibrary ? "Selected from Templates/" : "Template library"}
                    </span>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => setTemplatePickerOpen(true)}
                        className="ghost-btn px-3 py-2 text-xs"
                      >
                        Change template
                      </button>
                      <button
                        type="button"
                        disabled={!selectedResumeId || !hasActiveTemplate || resumeExportLoading === "docx"}
                        onClick={() => onResumeExport("docx")}
                        className="ghost-btn px-3 py-2 text-xs disabled:opacity-45"
                      >
                        {resumeExportLoading === "docx" ? "..." : "Download TEX"}
                      </button>
                      <button
                        type="button"
                        disabled={!selectedResumeId || !hasActiveTemplate || resumeExportLoading === "pdf"}
                        onClick={() => onResumeExport("pdf")}
                        className="primary-btn px-3 py-2 text-xs disabled:opacity-45"
                      >
                        {resumeExportLoading === "pdf" ? "..." : "Download PDF"}
                      </button>
                    </div>
                  </div>
                  {effectiveTemplateId ? (
                    <DocxTemplatePreview
                      template={currentTemplate}
                      templateId={effectiveTemplateId}
                      resume={selectedResume}
                    />
                  ) : (
                    <p className="text-sm text-amber-300/90">Add templates in backend config and refresh this page.</p>
                  )}
                </div>

                {selectedResume ? (
                  <div className="animate-fade-in-up">
                    <ResumeStructureEditor resume={selectedResume} onSaved={loadResumes} title="Resume fields (editable)" />
                  </div>
                ) : null}

                <div className="flex flex-wrap justify-end gap-2 sm:gap-3">
                  <button type="button" onClick={() => goTab("jobs")} className="ghost-btn w-full px-5 py-2.5 sm:w-auto">
                    Job search
                  </button>
                  <button type="button" onClick={() => goTab("tailor")} className="primary-btn w-full px-5 py-2.5 sm:w-auto">
                    JD tailor
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {hub === HUB_AI && tab === "tailor" && (
          <section className="space-y-6">
            <WorkflowProgress
              eyebrow="Tailoring flow"
              title="Use the selected resume and template, analyze the JD, then generate the tailored version"
              description="This keeps the tailoring experience structured and professional instead of exposing disconnected actions."
              steps={tailorWorkflowSteps}
            />
            {resumes.length === 0 ? (
              <div className="mx-auto max-w-lg animate-fade-in-up">
                <div className="panel panel-interactive overflow-hidden p-6 sm:p-8">
                  <div className="animate-stagger-1 text-center">
                    <div className="mx-auto mb-4 flex h-16 w-16 animate-float items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/25 to-indigo-600/30 text-3xl shadow-lg shadow-violet-900/30">
                      🎯
                    </div>
                    <p className="text-lg font-semibold text-white">Upload a resume to continue</p>
                    <p className="mt-2 text-sm leading-relaxed text-slate-400 sm:text-base">
                      Then paste a job description to generate a tailored version and PDF.
                    </p>
                  </div>
                  <label className="upload-dropzone mx-auto mt-8 block max-w-md cursor-pointer animate-stagger-2">
                    <input
                      type="file"
                      accept=".pdf,.docx,.doc,.txt"
                      className="sr-only"
                      onChange={(e) => onUpload(e, "ai-tailor")}
                      disabled={uploading}
                    />
                    <span className="pointer-events-none flex flex-col items-center gap-2">
                      <span className="font-display text-base font-semibold text-white">
                        {uploading ? "Uploading…" : "Upload resume to continue"}
                      </span>
                      <span className="text-xs text-slate-500">PDF, DOCX, or TXT</span>
                    </span>
                  </label>
                  <p className="animate-stagger-3 mt-6 text-center text-xs text-slate-500">
                    <button
                      type="button"
                      className="font-medium text-cyan-400 underline decoration-cyan-500/40 underline-offset-2 hover:text-cyan-300"
                      onClick={() => goTab("enhance")}
                    >
                      Back to ATS enhancement
                    </button>
                  </p>
                </div>
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
                  <p className="text-sm text-slate-400">Paste a JD, keep the selected template, and generate a polished tailored PDF.</p>
                  <button
                    type="button"
                    onClick={() => goTab("enhance")}
                    className="text-sm font-medium text-cyan-300 hover:underline"
                  >
                    ← ATS enhancement
                  </button>
                </div>

                <div className="panel panel-interactive space-y-3 p-4 sm:p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-300">
                    <span>Template:</span>
                    <span className="font-semibold text-white">{selectedTemplateName}</span>
                    <span className="text-xs text-slate-500">
                      {usingFolderTemplateLibrary ? "Selected from Templates/" : "Template library"}
                    </span>
                    <button
                      type="button"
                      onClick={() => setTemplatePickerOpen(true)}
                      className="ghost-btn px-3 py-2 text-xs"
                    >
                      Change template
                    </button>
                  </div>
                  {effectiveTemplateId ? (
                    <DocxTemplatePreview
                      template={currentTemplate}
                      templateId={effectiveTemplateId}
                      resume={selectedResume}
                    />
                  ) : (
                    <p className="text-sm text-amber-300/90">Add supported templates from the Career hub.</p>
                  )}
                </div>

                <p className="panel-interactive rounded-xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
                  Edits live in{" "}
                  <button type="button" className="font-semibold text-cyan-300 underline" onClick={() => goTab("enhance")}>
                    ATS enhancement
                  </button>
                  .
                </p>

                <div className="grid gap-6 lg:grid-cols-2">
                  <div className="panel panel-interactive space-y-4 p-5 sm:p-6">
                    <h2 className="font-display text-base font-semibold text-white">Job description</h2>
                    <textarea
                      className="input-dark min-h-[200px] resize-y"
                      placeholder="Paste the full JD text..."
                      value={jdText}
                      onChange={(e) => setJdText(e.target.value)}
                    />
                    <button
                      type="button"
                      onClick={analyzeJd}
                      disabled={jdLoading}
                      className="primary-btn px-4 py-2 text-sm disabled:opacity-50"
                    >
                      {jdLoading ? "Analyzing..." : "Analyze JD"}
                    </button>
                    {jdRow && (
                      <div className="space-y-2 text-sm text-slate-300">
                        <p className="font-medium text-white">Keywords</p>
                        <p className="mt-1 text-xs text-slate-400">{(jdRow.parsed_json?.must_have_keywords || []).join(", ")}</p>
                        <button
                          type="button"
                          className="text-xs font-medium text-cyan-300 hover:underline"
                          onClick={() => goTab("jobs")}
                        >
                          Open job search (uses your resume, not this JD)
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="panel panel-interactive space-y-4 p-5 sm:p-6">
                    <h2 className="font-display text-base font-semibold text-white">Tailored resume</h2>
                    <label className="block text-sm text-slate-300">
                      Active resume
                      <select
                        className="mt-1 input-dark py-2.5"
                        value={selectedResumeId ?? ""}
                        onChange={(e) => setSelectedResumeId(Number(e.target.value))}
                      >
                        {resumes.map((r) => (
                          <option key={r.id} value={r.id} className="bg-slate-900">
                            {resumeFileLabel(r)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="ghost-btn block w-full cursor-pointer !justify-center text-center text-xs sm:text-sm">
                      <input
                        type="file"
                        accept=".pdf,.docx,.doc,.txt"
                        className="hidden"
                        onChange={(e) => onUpload(e, "ai-tailor")}
                        disabled={uploading}
                      />
                      {uploading ? "Uploading…" : "Upload another resume"}
                    </label>
                    <button
                      type="button"
                      onClick={runTailor}
                      disabled={tailorLoading || !jdRow || !selectedResumeId || !hasActiveTemplate}
                      className="w-full rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 py-2.5 text-sm font-semibold text-white shadow-lg transition-transform duration-200 hover:brightness-110 active:scale-[0.99] disabled:opacity-50"
                    >
                      {tailorLoading ? "Generating..." : "Generate tailored resume"}
                    </button>
                    {tailorSession && (
                      <div className="space-y-3">
                        <p className="text-sm text-slate-300">
                          Tailored ATS score:{" "}
                          <span className="font-bold text-cyan-400">{Math.round(tailorSession.ats_score)}</span>
                        </p>
                        <button
                          type="button"
                          onClick={onDownloadPdf}
                          disabled={pdfLoading}
                          className="primary-btn w-full py-2.5 disabled:opacity-50"
                        >
                          {pdfLoading ? "Preparing PDF..." : "Download tailored PDF"}
                        </button>
                        <pre className="max-h-64 overflow-auto rounded-xl border border-white/10 bg-black/40 p-4 text-xs text-slate-200">
                          {JSON.stringify(tailorSession.output_resume_json, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </section>
        )}

        {hub === HUB_CAREER && tab === "jobs" && (
          <section className="grid gap-6 lg:grid-cols-2">
            <div className="panel p-6 space-y-4">
              <p className="text-sm text-slate-300">
                With a resume, the API <span className="font-semibold text-white">generates several job titles</span> in your
                field (from your experience, skills, and summary — any industry), then{" "}
                <span className="font-semibold text-white">runs a full board search per title</span> using your estimated
                experience so results match your level. Results come from{" "}
                <span className="font-semibold text-white">LinkedIn, Indeed, and Google Jobs</span> ({jobBoardRegionLabel}
                ), plus optional <span className="font-semibold text-white">web search</span> for company / ATS pages when{" "}
                <span className="font-mono text-slate-300">SERPAPI_KEY</span> is set. Listings are then{" "}
                <span className="text-cyan-200/90 font-medium">AI-shortlisted</span> for JD fit.{" "}
                <span className="text-slate-400">Work type</span> and <span className="text-slate-400">Date posted</span> filter
                instantly — click <span className="font-medium text-slate-200">Search jobs</span> to refresh. If a JD is
                blank, use <span className="font-medium text-slate-200">Load description</span> below.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => fetchJSearchJobs(false)}
                  disabled={jobsLoading}
                  className="primary-btn px-5 py-2.5 text-sm font-semibold disabled:opacity-50"
                >
                  {jobsLoading ? "Searching…" : "Search jobs"}
                </button>
                {!selectedResumeId && (
                  <span className="text-xs text-amber-200/90">Select or upload a resume for AI-suggested titles.</span>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <label className="text-sm text-slate-300">
                  Country / region
                  <input
                    className="mt-1 input-dark"
                    list="job-country-options"
                    placeholder="Search country or keep Global"
                    value={jobCountrySearch}
                    onChange={(e) => onCountryInputChange(e.target.value)}
                    onBlur={onCountryInputBlur}
                  />
                  <datalist id="job-country-options">
                    {COUNTRY_OPTIONS.map((c) => (
                      <option key={c.code || "global"} value={c.label} />
                    ))}
                  </datalist>
                </label>
                <label className="text-sm text-slate-300">
                  Work type
                  <select
                    className="mt-1 input-dark py-2.5"
                    value={jobWorkType}
                    onChange={(e) => setJobWorkType(e.target.value)}
                  >
                    <option value="all" className="bg-slate-900">
                      All
                    </option>
                    <option value="remote" className="bg-slate-900">
                      Remote
                    </option>
                    <option value="on-site" className="bg-slate-900">
                      On-site
                    </option>
                  </select>
                </label>
                <label className="text-sm text-slate-300 sm:col-span-2 lg:col-span-1">
                  Date posted
                  <select
                    className="mt-1 input-dark py-2.5"
                    value={jobDatePosted}
                    onChange={(e) => setJobDatePosted(e.target.value)}
                  >
                    <option value="all" className="bg-slate-900">
                      Any time
                    </option>
                    <option value="today" className="bg-slate-900">
                      Today
                    </option>
                    <option value="3days" className="bg-slate-900">
                      Last 3 days
                    </option>
                    <option value="week" className="bg-slate-900">
                      Last week
                    </option>
                    <option value="month" className="bg-slate-900">
                      Last month
                    </option>
                  </select>
                </label>
              </div>
              {jobSearchMeta.suggestedRoles?.length > 0 && (
                <p className="text-xs rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2 text-slate-300">
                  <span className="font-semibold text-white">Roles targeted:</span>{" "}
                  {jobSearchMeta.suggestedRoles.join(" · ")}
                </p>
              )}
              {jobSearchMeta.experienceYears != null && (
                <p className="text-xs rounded-xl border border-cyan-500/25 bg-cyan-950/30 text-cyan-100/90 px-3 py-2">
                  <span className="font-semibold text-cyan-200">Experience targeting:</span> ~{jobSearchMeta.experienceYears}{" "}
                  year
                  {jobSearchMeta.experienceYears === 1 ? "" : "s"} from your resume
                  {jobSearchMeta.experiencePhrase ? (
                    <>
                      {" "}
                      — queries include <span className="font-medium">"{jobSearchMeta.experiencePhrase}"</span>
                    </>
                  ) : null}
                  .
                </p>
              )}
              <details className="rounded-xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
                <summary className="font-medium text-white cursor-pointer">Advanced: custom search text</summary>
                <p className="mt-2 text-xs text-slate-500 leading-relaxed">
                  Adds openings for this role to the list below — your existing resume-based results stay. Duplicate jobs
                  (same id) are skipped; newest combined list is sorted by match %.
                </p>
                <div className="mt-3 flex gap-2">
                  <input
                    className="flex-1 input-dark"
                    placeholder="e.g. Data Analyst, Product Manager"
                    value={jobQuery}
                    onChange={(e) => setJobQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && runManualJobSearch()}
                  />
                  <button
                    type="button"
                    onClick={runManualJobSearch}
                    disabled={jobsLoading}
                    className="primary-btn px-4 py-2 text-sm disabled:opacity-50 shrink-0"
                  >
                    {jobsLoading ? "…" : "Add to results"}
                  </button>
                </div>
              </details>
              {jobSearchMeta.queries?.length > 0 && (
                <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-400">
                  <span className="font-semibold text-slate-200">Board searches ({jobBoardRegionLabel}):</span>{" "}
                  {jobSearchMeta.queries.join(" · ")}
                </div>
              )}
              {jobSearchMeta.message && <p className="text-xs text-slate-500">{jobSearchMeta.message}</p>}
              <p className="text-xs text-slate-500">
                {selectedResume ? resumeFileLabel(selectedResume) : "No resume"} ·{" "}
                <span className="text-cyan-200/80">Work type / date</span> filter the last search instantly ·{" "}
                <span className="text-slate-400 font-medium">Search jobs</span> hits boards (may be rate-limited).
              </p>
              <ul className="space-y-2 max-h-[560px] overflow-auto">
                {!jobsLoading && jobScrapePool.length === 0 && (
                  <li className="rounded-xl border border-dashed border-white/15 bg-slate-950/30 px-4 py-8 text-center text-sm text-slate-500">
                    No listings yet — click <span className="text-slate-300 font-medium">Search jobs</span> to run a fresh
                    scrape (not shared with Tracker).
                  </li>
                )}
                {!jobsLoading && jobScrapePool.length > 0 && jobsFiltered.length === 0 && (
                  <li className="rounded-xl border border-amber-500/25 bg-amber-950/20 px-4 py-6 text-center text-sm text-amber-100/90">
                    No jobs match <span className="font-medium">Work type</span> / <span className="font-medium">Date posted</span>.
                    Widen filters or run <span className="font-medium">Search jobs</span> again.
                  </li>
                )}
                {jobsFiltered.map((j) => (
                  <li key={j.id}>
                    <button
                      type="button"
                      onClick={() => setJobDetail(j)}
                      className={`w-full text-left rounded-xl border p-3 text-sm transition ${
                        jobDetail?.id === j.id
                          ? "border-cyan-500/50 bg-cyan-950/30"
                          : "border-white/10 hover:border-white/20 bg-slate-950/20"
                      }`}
                    >
                      <p className="font-semibold text-white">{j.title}</p>
                      <p className="text-slate-400 text-xs mt-0.5">
                        {j.company} · {j.location} · {j.source}
                      </p>
                      {j.match_score != null && (
                        <p className="text-cyan-400 text-xs mt-1 font-medium">Match {Math.round(j.match_score)}%</p>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div className="panel p-6 min-h-[320px]">
              {jobDetail ? (
                <div className="space-y-4">
                  <div>
                    <h2 className="text-lg font-bold text-white">{jobDetail.title}</h2>
                    <p className="text-sm text-slate-400">
                      {jobDetail.company} · {jobDetail.location}
                    </p>
                    {jobDetail.fit_rationale && (
                      <p className="mt-3 rounded-xl border border-cyan-500/25 bg-cyan-950/25 px-3 py-2 text-xs leading-relaxed text-cyan-100/90">
                        <span className="font-semibold text-cyan-300">AI fit: </span>
                        {jobDetail.fit_rationale}
                      </p>
                    )}
                  </div>
                  <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed max-h-[min(70vh,640px)] overflow-y-auto rounded-lg border border-white/10 bg-slate-950/40 p-4">
                    {jobDetail.description?.trim() ? (
                      jobDetail.description
                    ) : (
                      <div className="space-y-3 text-slate-400">
                        <p>
                          No job description text for this listing yet (some boards only return a title until the page is
                          opened).
                        </p>
                        {jobDetail.apply_url ? (
                          <button
                            type="button"
                            onClick={refreshJobDetailDescription}
                            disabled={jobDescRefreshLoading}
                            className="rounded-xl border border-cyan-500/40 bg-cyan-950/40 px-3 py-2 text-xs font-medium text-cyan-100 hover:bg-cyan-950/60 disabled:opacity-50"
                          >
                            {jobDescRefreshLoading ? "Loading…" : "Load description from job page"}
                          </button>
                        ) : (
                          <p className="text-xs text-slate-500">No apply link is available for this role.</p>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {jobDetail.skills?.map((s) => (
                      <span
                        key={s}
                        className={`text-xs px-2 py-1 rounded-full ${
                          jobDetail.matching_skills?.includes(s)
                            ? "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30"
                            : "bg-amber-500/15 text-amber-200 border border-amber-500/25"
                        }`}
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => saveJob(jobDetail, "saved")}
                      className="ghost-btn px-3 py-2 text-sm"
                    >
                      Save to tracker
                    </button>
                    <button
                      type="button"
                      onClick={() => saveJob(jobDetail, "applied")}
                      className="primary-btn px-3 py-2 text-sm"
                    >
                      Mark applied
                    </button>
                    {jobDetail.apply_url && (
                      <a
                        href={jobDetail.apply_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center px-3 py-2 rounded-xl border border-white/15 text-sm text-slate-200 hover:bg-white/5"
                      >
                        Open apply link
                      </a>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">Select a job to view details.</p>
              )}
            </div>
          </section>
        )}

        {hub === HUB_CAREER && tab === "tracker" && (
          <section className="space-y-6">
            <p className="text-sm text-slate-400 max-w-2xl">
              Visualize your pipeline from saved roles through offers. Update each card’s status as you progress.
            </p>

            <TrackerAnalytics apps={apps} stages={TRACK_STAGES} />

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {TRACK_STAGES.map((stage) => (
                <div key={stage} className="panel p-4">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">{stage.replace("_", " ")}</h3>
                  <ul className="mt-3 space-y-2">
                    {apps
                      .filter((a) => a.status === stage)
                      .map((a) => {
                        const j = jobsById[a.job_id];
                        return (
                          <li
                            key={a.id}
                            className="rounded-xl border border-white/10 p-2 text-xs bg-slate-950/40"
                          >
                            <p className="font-semibold text-white">{j?.title || `Job #${a.job_id}`}</p>
                            <p className="text-slate-400">{j?.company}</p>
                            <select
                              className="mt-2 w-full text-xs rounded-lg border border-white/10 bg-slate-950/80 text-slate-200 p-1.5"
                              value={a.status}
                              onChange={(e) => patchApp(a.id, e.target.value)}
                            >
                              {TRACK_STAGES.map((s) => (
                                <option key={s} value={s} className="bg-slate-900">
                                  {s}
                                </option>
                              ))}
                            </select>
                          </li>
                        );
                      })}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
      </div>
    </div>
  );
}
