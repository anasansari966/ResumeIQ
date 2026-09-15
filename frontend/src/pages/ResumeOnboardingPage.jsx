import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Download, FileText, Loader2, Sparkles, UploadCloud } from "lucide-react";
import api from "../api";
import TemplatePreviewThumb from "../components/TemplatePreviewThumb";
import AnimatedResumePreview from "../components/AnimatedResumePreview";
import AccentColorPicker from "../components/AccentColorPicker";
import { useToast } from "../components/Toast";
import useAuth from "../hooks/useAuth";
import useResumes from "../hooks/useResumes";
import { isResumeOnboardingDone, setResumeOnboardingDone } from "../onboarding";
import { normalizeAccentHex } from "../theme/accentColors";

const MS_ATS_TEMPLATES_URL =
  "https://word.cloud.microsoft/search/ats/?wdOrigin=SEO-INTENT.WD-SE-L46-1-L46-1.SEARCHTEMPLATES";

function atsTone(score) {
  if (score >= 90) return "bg-emerald-100 text-emerald-700";
  if (score >= 80) return "bg-amber-100 text-amber-700";
  return "bg-gray-100 text-gray-700";
}

function progressWidthClass(progress) {
  const steps = [
    "w-0",
    "w-[5%]",
    "w-[10%]",
    "w-[15%]",
    "w-[20%]",
    "w-[25%]",
    "w-[30%]",
    "w-[35%]",
    "w-[40%]",
    "w-[45%]",
    "w-1/2",
    "w-[55%]",
    "w-[60%]",
    "w-[65%]",
    "w-[70%]",
    "w-[75%]",
    "w-[80%]",
    "w-[85%]",
    "w-[90%]",
    "w-[95%]",
    "w-full",
  ];
  const idx = Math.max(0, Math.min(20, Math.round(Number(progress || 0) / 5)));
  return steps[idx];
}

export default function ResumeOnboardingPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { user } = useAuth();
  const { downloadResume } = useResumes();
  const isReturning = Boolean(user?.id && isResumeOnboardingDone(user.id));

  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedResume, setUploadedResume] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [accentColor, setAccentColor] = useState("#0f766e");
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [templateReady, setTemplateReady] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importName, setImportName] = useState("");
  const [importing, setImporting] = useState(false);
  const stepTwoRef = useRef(null);

  const sortedTemplates = useMemo(
    () => [...templates].sort((a, b) => Number(b.ats_score || 0) - Number(a.ats_score || 0)),
    [templates],
  );

  const fetchTemplates = async () => {
    setTemplatesLoading(true);
    try {
      const response = await api.get("/templates");
      const rows = response.data || [];
      const ordered = [...rows].sort((a, b) => Number(b.ats_score || 0) - Number(a.ats_score || 0));
      setTemplates(ordered);
      if (ordered[0]) {
        setSelectedTemplateId(ordered[0].id);
      }
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Failed to load templates." });
    } finally {
      setTemplatesLoading(false);
    }
  };

  const jumpToStepTwo = () => {
    window.setTimeout(() => {
      stepTwoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  };

  useEffect(() => {
    // Prefetch templates so Step 2 is ready right after upload.
    void fetchTemplates();
  }, []);

  const handleUpload = async () => {
    if (!file) {
      showToast({ type: "warning", message: "Please choose a resume file first." });
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    setUploadProgress(8);

    const progressTimer = window.setInterval(() => {
      setUploadProgress((p) => (p >= 90 ? p : Math.min(90, p + 7)));
    }, 280);

    try {
      const response = await api.post("/resumes/upload", formData, {
        timeout: 120000,
        onUploadProgress: (event) => {
          if (!event.total) return;
          const percent = Math.round((event.loaded * 100) / event.total);
          setUploadProgress(Math.max(percent, 15));
        },
      });

      setUploadProgress(100);
      const resume = response.data;
      setUploadedResume(resume);
      setStep(2);
      showToast({ type: "success", message: "Resume uploaded. Choose an ATS template below." });
      await fetchTemplates();
      jumpToStepTwo();
    } catch (error) {
      const detail =
        error?.response?.data?.detail ||
        (typeof error?.response?.data === "string" ? error.response.data : "") ||
        error?.message ||
        "Resume upload failed.";
      showToast({ type: "error", message: detail });
    } finally {
      window.clearInterval(progressTimer);
      setUploading(false);
    }
  };

  useEffect(() => {
    if (step >= 2 && !templatesLoading) {
      jumpToStepTwo();
    }
  }, [step, templatesLoading]);

  const applyAtsTemplate = async ({ downloadAfter = false } = {}) => {
    if (!uploadedResume?.id || !selectedTemplateId) {
      showToast({ type: "warning", message: "Please upload a resume and select a template." });
      return null;
    }

    setApplyingTemplate(true);
    setTemplateReady(false);
    try {
      const { data } = await api.post(
        `/resumes/${uploadedResume.id}/select-template`,
        {
          template_id: selectedTemplateId,
          accent_color: normalizeAccentHex(accentColor),
          restructure: true,
        },
        { timeout: 300000 },
      );
      setUploadedResume(data);
      setTemplateReady(true);
      if (user?.id) {
        setResumeOnboardingDone(user.id);
      }
      showToast({
        type: "success",
        message: downloadAfter
          ? "Resume structured into the ATS template. Starting download…"
          : "LLM structured your resume into the ATS template. Download when ready.",
      });

      if (downloadAfter) {
        const safeName = (selectedTemplateId || "ats").replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 40);
        setDownloading(true);
        await downloadResume(data.id, "pdf", selectedTemplateId, `resume-${data.id}-${safeName}`);
        showToast({ type: "success", message: "Updated ATS resume downloaded." });
      }
      return data;
    } catch (error) {
      showToast({
        type: "error",
        message: error.response?.data?.detail || (downloadAfter ? "Download failed." : "Could not apply template."),
      });
      return null;
    } finally {
      setApplyingTemplate(false);
      setDownloading(false);
    }
  };

  const continueWithTemplate = () => applyAtsTemplate({ downloadAfter: false });

  const downloadUpdatedResume = async () => {
    if (templateReady && uploadedResume?.id) {
      setDownloading(true);
      try {
        const safeName = (selectedTemplateId || "ats").replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 40);
        await downloadResume(
          uploadedResume.id,
          "pdf",
          selectedTemplateId,
          `resume-${uploadedResume.id}-${safeName}`,
        );
        showToast({ type: "success", message: "Updated ATS resume downloaded." });
      } catch {
        /* toast in hook */
      } finally {
        setDownloading(false);
      }
      return;
    }
    await applyAtsTemplate({ downloadAfter: true });
  };

  const importTemplateFromWeb = async () => {
    const url = importUrl.trim();
    if (!url) {
      showToast({ type: "warning", message: "Paste a LaTeX template URL first." });
      return;
    }

    setImporting(true);
    try {
      const response = await api.post("/templates/import-web", {
        url,
        name: importName.trim() || undefined,
      });
      const importedId = response.data?.id || "";
      showToast({ type: "success", message: "Web LaTeX template imported successfully." });
      await fetchTemplates();
      if (importedId) {
        setSelectedTemplateId(importedId);
      }
      setImportUrl("");
      setImportName("");
      jumpToStepTwo();
    } catch (error) {
      const detail =
        error?.response?.data?.detail ||
        (typeof error?.response?.data === "string" ? error.response.data : "") ||
        error?.message ||
        "Template import failed.";
      showToast({ type: "error", message: detail });
    } finally {
      setImporting(false);
    }
  };

  const goReupload = () => {
    setFile(null);
    setUploadedResume(null);
    setStep(1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="space-y-6">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        {isReturning ? (
          <section className="surface-card border border-teal-100 bg-white">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-teal-600">Resume setup</p>
                <h2 className="mt-1 text-xl font-bold text-gray-900">You have already completed first-time setup</h2>
                <p className="mt-1 max-w-2xl text-sm text-gray-600">
                  Open the dashboard to edit your resume and change templates, or upload a new file here to add or replace
                  a resume.
                </p>
              </div>
              <div className="flex flex-shrink-0 flex-wrap gap-2">
                <button type="button" className="btn-secondary" onClick={() => navigate("/dashboard")}>
                  Dashboard — edit and templates
                </button>
                <button type="button" className="btn-primary" onClick={goReupload}>
                  Re-upload resume
                </button>
              </div>
            </div>
          </section>
        ) : null}

        <section className="surface-card bg-gradient-to-r from-[#0b1324] to-teal-900 text-white">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">ResumeIQ Onboarding</p>
          <h1 className="mt-2 text-3xl font-bold">
            {isReturning ? "Add another resume or switch templates from the dashboard" : "Upload your resume, then pick an ATS-friendly template"}
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-300">
            {isReturning
              ? "Use Re-upload below to parse a new file, or go to the dashboard to edit an existing resume and its template."
              : "We will parse your resume first, show upload progress clearly, and then let you choose top ATS templates to generate a better scoring resume."}
          </p>
        </section>

        <section className="surface-card">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={`rounded-xl border p-4 ${step >= 1 ? "border-teal-300 bg-teal-50" : "border-gray-200 bg-white"}`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-teal-600">Step 1</p>
              <p className="mt-1 text-sm font-semibold text-gray-900">Upload Resume</p>
              <p className="mt-1 text-xs text-gray-500">Upload PDF, DOC, DOCX, or TXT</p>
            </div>
            <div className={`rounded-xl border p-4 ${step >= 2 ? "border-teal-300 bg-teal-50" : "border-gray-200 bg-white"}`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-teal-600">Step 2</p>
              <p className="mt-1 text-sm font-semibold text-gray-900">Select ATS Template</p>
              <p className="mt-1 text-xs text-gray-500">Choose the best ATS score template</p>
            </div>
          </div>
        </section>

        <section className="surface-card">
          <div className="grid gap-6 lg:grid-cols-[1fr,auto] lg:items-end">
            <div>
              <label className="mb-2 block text-sm font-semibold text-gray-800">Choose your resume file</label>
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-gray-300 bg-white px-4 py-4 hover:border-teal-400">
                <UploadCloud className="h-5 w-5 text-teal-600" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-gray-900">
                    {file ? file.name : "Click to upload your resume"}
                  </p>
                  <p className="text-xs text-gray-500">Max parsing reliability with PDF or DOCX.</p>
                </div>
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.doc,.docx,.txt"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
              </label>
            </div>
            <button type="button" className="btn-primary h-fit" onClick={handleUpload} disabled={uploading || !file}>
              {uploading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Uploading...
                </span>
              ) : (
                "Upload Resume"
              )}
            </button>
          </div>

          {uploading ? (
            <div className="mt-4 rounded-xl border border-teal-200 bg-teal-50 p-4">
              <div className="mb-2 flex items-center justify-between text-sm font-medium text-teal-700">
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Upload in progress
                </span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-teal-100">
                <div className={`h-full bg-teal-500 ${progressWidthClass(uploadProgress)}`} />
              </div>
            </div>
          ) : null}

          {uploadedResume ? (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <p className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                Resume uploaded successfully
              </p>
              <div className="mt-2 grid gap-2 text-sm text-emerald-800 sm:grid-cols-2">
                <p className="inline-flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  {uploadedResume.file_name || `Resume #${uploadedResume.id}`}
                </p>
                <p>
                  Current ATS Baseline:{" "}
                  <span className="font-semibold">{Math.round(Number(uploadedResume.ats_baseline || 0))}/100</span>
                </p>
              </div>
              {step < 2 ? (
                <button
                  type="button"
                  className="btn-primary mt-3"
                  onClick={() => {
                    setStep(2);
                    void fetchTemplates();
                    jumpToStepTwo();
                  }}
                >
                  Continue to ATS templates
                </button>
              ) : (
                <button type="button" className="mt-3 text-sm font-semibold text-teal-700 hover:text-teal-800" onClick={jumpToStepTwo}>
                  Scroll to template picker ↓
                </button>
              )}
            </div>
          ) : null}
        </section>

        {step >= 2 ? (
          <section ref={stepTwoRef} className="surface-card">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-teal-600">ATS Templates</p>
                <h2 className="text-xl font-bold text-gray-900">Select a Word-style ATS template</h2>
                <p className="mt-1 text-sm text-gray-500">
                  Pick a template and accent. ResumeIQ uses OpenAI to structure your extracted content into clean ATS
                  sections, then you can download the updated PDF.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <a
                  href={MS_ATS_TEMPLATES_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="btn-secondary text-sm"
                >
                  Microsoft ATS gallery
                </a>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={applyingTemplate || downloading || !selectedTemplateId || !uploadedResume}
                  onClick={() => void continueWithTemplate()}
                >
                  {applyingTemplate && !downloading ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Structuring with AI...
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Structure with AI
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={applyingTemplate || downloading || !selectedTemplateId || !uploadedResume}
                  onClick={() => void downloadUpdatedResume()}
                >
                  {downloading || (applyingTemplate && downloading) ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Preparing PDF...
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2">
                      <Download className="h-4 w-4" />
                      Download updated resume
                    </span>
                  )}
                </button>
              </div>
            </div>

            {templateReady ? (
              <div className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-800">
                  <CheckCircle2 className="h-4 w-4" />
                  ATS template applied — content restructured for{" "}
                  {sortedTemplates.find((t) => t.id === selectedTemplateId)?.name || "selected template"}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-primary gap-2"
                    disabled={downloading}
                    onClick={() => void downloadUpdatedResume()}
                  >
                    <Download className="h-4 w-4" />
                    Download PDF
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => navigate(`/resume/${uploadedResume.id}/edit`)}
                  >
                    Open editor
                  </button>
                </div>
              </div>
            ) : null}
            <div className="mb-5 rounded-xl border border-gray-200 bg-white p-4">
              <p className="text-sm font-semibold text-gray-900">Import LaTeX template from web</p>
              <p className="mt-1 text-xs text-gray-500">
                Paste a direct `.tex` URL (for GitHub, use raw URL or blob URL).
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-[1fr,220px,auto]">
                <input
                  className="input-base"
                  placeholder="https://raw.githubusercontent.com/.../resume.tex"
                  value={importUrl}
                  onChange={(event) => setImportUrl(event.target.value)}
                />
                <input
                  className="input-base"
                  placeholder="Template name (optional)"
                  value={importName}
                  onChange={(event) => setImportName(event.target.value)}
                />
                <button type="button" className="btn-secondary" onClick={importTemplateFromWeb} disabled={importing}>
                  {importing ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Importing...
                    </span>
                  ) : (
                    "Import URL"
                  )}
                </button>
              </div>
            </div>

            {templatesLoading ? (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 6 }).map((_, idx) => (
                  <div key={idx} className="animate-pulse rounded-xl border border-gray-200 p-4">
                    <div className="h-24 rounded-lg bg-gray-100" />
                    <div className="mt-3 h-4 w-2/3 rounded bg-gray-100" />
                    <div className="mt-2 h-3 w-1/2 rounded bg-gray-100" />
                  </div>
                ))}
              </div>
            ) : sortedTemplates.length ? (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
                    <AccentColorPicker
                      value={accentColor}
                      onChange={(hex) => {
                        setAccentColor(hex);
                        setTemplateReady(false);
                      }}
                    />
                    <p className="mt-2 text-xs text-slate-500">
                      Accent updates the live preview instantly and is saved with your resume for PDF export.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {sortedTemplates.map((template) => {
                      const active = selectedTemplateId === template.id;
                      return (
                        <button
                          key={template.id}
                          type="button"
                          onClick={() => {
                            setSelectedTemplateId(template.id);
                            setTemplateReady(false);
                          }}
                          className={`rounded-xl border p-3 text-left transition ${
                            active ? "border-teal-500 bg-teal-50 ring-1 ring-teal-200" : "border-gray-200 bg-white hover:border-teal-300"
                          }`}
                        >
                          <div className="mb-3 h-24 overflow-hidden rounded-lg border border-gray-100 bg-gray-50">
                            <TemplatePreviewThumb
                              templateId={template.id}
                              previewUrl={template.preview_url}
                              heightClass="h-24"
                              fallbackClassName="bg-gradient-to-br from-teal-100 to-teal-200"
                            />
                          </div>
                          <p className="text-sm font-semibold text-gray-900">{template.name}</p>
                          <p className="mt-1 line-clamp-2 text-xs text-gray-500">{template.best_for || template.style}</p>
                          <div className="mt-3 flex items-center justify-between">
                            <span className={`rounded-lg px-2 py-1 text-xs font-semibold ${atsTone(template.ats_score)}`}>
                              ATS {Number(template.ats_score || 0)}/100
                            </span>
                            {active ? <span className="text-xs font-semibold text-teal-700">Selected</span> : null}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="xl:sticky xl:top-24 xl:self-start">
                  <div className="rounded-xl border border-teal-100 bg-white p-4 shadow-sm">
                    <div className="mb-3">
                      <p className="text-sm font-semibold text-gray-900">Live preview</p>
                      <p className="text-xs text-gray-500">
                        {sortedTemplates.find((t) => t.id === selectedTemplateId)?.name || "Template"} · accent{" "}
                        {normalizeAccentHex(accentColor)}
                      </p>
                    </div>
                    {selectedTemplateId && uploadedResume ? (
                      <AnimatedResumePreview
                        key={`${selectedTemplateId}-${accentColor}-${templateReady}-${uploadedResume?.updated_at || uploadedResume?.id}`}
                        template={sortedTemplates.find((t) => t.id === selectedTemplateId)}
                        templateId={selectedTemplateId}
                        resume={{
                          ...(uploadedResume.parsed_json || uploadedResume),
                          accent_color: normalizeAccentHex(accentColor),
                        }}
                        accentColor={normalizeAccentHex(accentColor)}
                        className="rounded-xl border border-slate-100 bg-slate-50/80 p-2"
                      />
                    ) : (
                      <p className="text-sm text-slate-500">Upload a resume and pick a template to preview.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-gray-200 bg-white p-6 text-center">
                <p className="text-sm text-gray-600">No templates available right now. Please try again.</p>
                <button type="button" className="btn-secondary mt-3" onClick={() => void fetchTemplates()}>
                  Reload templates
                </button>
              </div>
            )}
          </section>
        ) : null}
      </div>
    </div>
  );
}
