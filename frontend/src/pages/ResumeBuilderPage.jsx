import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import api from "../api";
import TemplatePreviewThumb from "../components/TemplatePreviewThumb";
import AnimatedResumePreview from "../components/AnimatedResumePreview";
import AccentColorPicker from "../components/AccentColorPicker";
import useResumes from "../hooks/useResumes";
import { useToast } from "../components/Toast";
import { normalizeAccentHex } from "../theme/accentColors";

const STEPS = ["Personal Info", "Work Experience", "Education", "Skills", "Template & Export"];

const EMPTY_EXPERIENCE = {
  title: "",
  company: "",
  location: "",
  start_date: "",
  end_date: "",
  current: false,
  description: "",
};

const EMPTY_EDUCATION = {
  degree: "",
  institution: "",
  field: "",
  start_year: "",
  end_year: "",
  gpa: "",
};

function initialsTemplateClass(index) {
  const styles = [
    "from-teal-100 to-teal-200",
    "from-emerald-100 to-emerald-200",
    "from-amber-100 to-amber-200",
    "from-rose-100 to-rose-200",
    "from-sky-100 to-sky-200",
    "from-violet-100 to-violet-200",
  ];
  return styles[index % styles.length];
}

function StepProgress({ step }) {
  const widthClass = ["w-0", "w-1/5", "w-2/5", "w-3/5", "w-4/5", "w-full"][step] || "w-0";
  return (
    <div className="surface-card">
      <div className="mb-3 flex flex-wrap gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        {STEPS.map((label, index) => (
          <span key={label} className={index + 1 <= step ? "text-teal-600" : ""}>
            {index + 1}. {label}
          </span>
        ))}
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-200">
        <div className={`h-full bg-teal-500 ${widthClass}`} />
      </div>
    </div>
  );
}

function TagInput({ label, values, onChange, placeholder }) {
  const [draft, setDraft] = useState("");

  const addTag = (raw) => {
    const next = String(raw || "").trim();
    if (!next) return;
    if (values.includes(next)) return;
    onChange([...values, next]);
    setDraft("");
  };

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">{label}</label>
      <div className="rounded-lg border border-gray-200 bg-white p-2">
        <div className="mb-2 flex flex-wrap gap-2">
          {values.map((item) => (
            <button
              key={item}
              type="button"
              className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-700"
              onClick={() => onChange(values.filter((v) => v !== item))}
            >
              {item} ×
            </button>
          ))}
        </div>
        <input
          className="w-full border-0 p-0 text-sm focus:outline-none"
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addTag(draft);
            }
          }}
        />
      </div>
    </div>
  );
}

function mapToParsedJson(form) {
  return {
    contact: {
      name: form.personal.fullName,
      email: form.personal.email,
      phone: form.personal.phone,
      location: form.personal.location,
      linkedin: form.personal.linkedin,
      portfolio: form.personal.portfolio,
    },
    summary: form.personal.summary,
    experience: form.experience.map((item) => ({
      title: item.title,
      company: item.company,
      location: item.location,
      start_date: item.start_date,
      end_date: item.current ? "Present" : item.end_date,
      bullets: item.description
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      description: item.description,
    })),
    education: form.education.map((item) => ({
      degree: item.degree,
      institution: item.institution,
      field: item.field,
      start_year: item.start_year,
      year: item.end_year,
      gpa: item.gpa,
    })),
    skills: {
      technical: form.skills.technical,
      tools: form.skills.certifications,
      languages: form.skills.languages,
      certifications: form.skills.certifications,
    },
    active_template_id: form.templateId,
    accent_color: normalizeAccentHex(form.accentColor || "#0f766e"),
  };
}

function suggestedSkillsFromExperience(experience) {
  const text = experience
    .map((item) => `${item.title} ${item.description}`)
    .join(" ")
    .toLowerCase();
  const dictionary = [
    "React",
    "TypeScript",
    "JavaScript",
    "Python",
    "SQL",
    "Node.js",
    "FastAPI",
    "REST API",
    "Docker",
    "AWS",
    "Leadership",
    "Communication",
  ];
  return dictionary.filter((skill) => text.includes(skill.toLowerCase()));
}

export default function ResumeBuilderPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { createResume, updateResume, generateSummary, downloadResume } = useResumes();

  const [step, setStep] = useState(1);
  const [resumeId, setResumeId] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [saving, setSaving] = useState(false);
  const [autoSaveStatus, setAutoSaveStatus] = useState("Not saved yet");
  const [errors, setErrors] = useState({});
  const [importUrl, setImportUrl] = useState("");
  const [importName, setImportName] = useState("");
  const [importingTemplate, setImportingTemplate] = useState(false);

  const [form, setForm] = useState({
    personal: {
      fullName: "",
      email: "",
      phone: "",
      location: "",
      linkedin: "",
      portfolio: "",
      summary: "",
    },
    experience: [{ ...EMPTY_EXPERIENCE }],
    education: [{ ...EMPTY_EDUCATION }],
    skills: {
      technical: [],
      languages: [],
      certifications: [],
    },
    templateId: "",
    accentColor: "#0f766e",
  });

  const serializedRef = useRef("");

  const fetchTemplates = useCallback(async () => {
    try {
      const response = await api.get("/templates");
      const list = response.data || [];
      setTemplates(list);
      setForm((prev) => (list[0] && !prev.templateId ? { ...prev, templateId: list[0].id } : prev));
      return list;
    } catch {
      showToast({ type: "error", message: "Could not load templates." });
      return [];
    }
  }, [showToast]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const parsedJson = useMemo(() => mapToParsedJson(form), [form]);

  const suggestedSkills = useMemo(() => suggestedSkillsFromExperience(form.experience), [form.experience]);

  const saveResume = async (isAuto = false) => {
    setSaving(true);
    try {
      let saved;
      if (resumeId) {
        saved = await updateResume(resumeId, parsedJson);
      } else {
        saved = await createResume(parsedJson);
        setResumeId(saved?.id || null);
      }

      const savedId = saved?.id || resumeId;
      if (savedId && form.templateId) {
        await api.post(`/resumes/${savedId}/select-template`, {
          template_id: form.templateId,
          accent_color: normalizeAccentHex(form.accentColor),
          restructure: true,
        });
      }

      const stamp = `Saved at ${new Date().toLocaleTimeString()}`;
      setAutoSaveStatus(stamp);
      serializedRef.current = JSON.stringify(parsedJson);
      if (!isAuto) showToast({ type: "success", message: "Resume saved successfully." });
      return savedId;
    } catch {
      if (!isAuto) showToast({ type: "error", message: "Could not save resume." });
      return null;
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const timer = window.setInterval(async () => {
      const currentSerialized = JSON.stringify(parsedJson);
      if (currentSerialized === serializedRef.current) return;
      await saveResume(true);
    }, 30000);
    return () => window.clearInterval(timer);
  }, [parsedJson]);

  const validateStep = () => {
    const nextErrors = {};

    if (step === 1) {
      if (!form.personal.fullName.trim()) nextErrors.fullName = "Full name is required.";
      if (!form.personal.email.trim()) nextErrors.email = "Email is required.";
    }

    if (step === 2) {
      if (!form.experience[0]?.title?.trim()) nextErrors.experience = "Add at least one job title.";
    }

    if (step === 3) {
      if (!form.education[0]?.degree?.trim()) nextErrors.education = "Add at least one education entry.";
    }

    if (step === 4) {
      if (!form.skills.technical.length) nextErrors.skills = "Add at least one skill.";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleNext = () => {
    if (!validateStep()) return;
    setStep((prev) => Math.min(prev + 1, 5));
  };

  const handlePrevious = () => setStep((prev) => Math.max(prev - 1, 1));

  const handleGenerateSummary = async () => {
    try {
      let id = resumeId;
      if (!id) {
        id = await saveResume(true);
        if (!id) return;
      }
      const updated = await generateSummary(id, parsedJson);
      const newSummary = updated?.parsed_json?.summary || "";
      setForm((prev) => ({ ...prev, personal: { ...prev.personal, summary: newSummary } }));
      showToast({ type: "success", message: "AI summary generated." });
    } catch {
      /* handled in hook */
    }
  };

  const aiEnhanceExperience = (index) => {
    setForm((prev) => {
      const next = [...prev.experience];
      const item = next[index];
      const description = item.description.trim();
      if (!description) return prev;
      next[index] = {
        ...item,
        description: description
          .split("\n")
          .map((line) => {
            const clean = line.trim();
            if (!clean) return "";
            return clean.startsWith("Led") || clean.startsWith("Built") ? clean : `Led ${clean.charAt(0).toLowerCase()}${clean.slice(1)}`;
          })
          .filter(Boolean)
          .join("\n"),
      };
      return { ...prev, experience: next };
    });
    showToast({ type: "info", message: "Experience text enhanced." });
  };

  const exportResume = async (kind) => {
    const id = (await saveResume(true)) || resumeId;
    if (!id) return;
    await downloadResume(id, kind === "pdf" ? "pdf" : "docx", form.templateId);
  };

  const importTemplateFromWeb = async () => {
    const url = importUrl.trim();
    if (!url) {
      showToast({ type: "warning", message: "Paste a LaTeX template URL first." });
      return;
    }

    setImportingTemplate(true);
    try {
      const response = await api.post("/templates/import-web", {
        url,
        name: importName.trim() || undefined,
      });
      const importedId = response.data?.id || "";
      await fetchTemplates();
      if (importedId) {
        setForm((prev) => ({ ...prev, templateId: importedId }));
      }
      setImportUrl("");
      setImportName("");
      showToast({ type: "success", message: "Template imported and selected." });
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Template import failed." });
    } finally {
      setImportingTemplate(false);
    }
  };

  return (
    <>
      <div className="space-y-6">
        <StepProgress step={step} />

        <div className="surface-card flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-gray-600">Auto-save status: {autoSaveStatus}</p>
          {saving ? <p className="text-sm font-medium text-teal-600">Saving...</p> : null}
        </div>

        {step === 1 ? (
          <section className="surface-card space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Step 1 — Personal Info</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Full Name</label>
                <input
                  className="input-base"
                  value={form.personal.fullName}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, personal: { ...prev.personal, fullName: event.target.value } }))
                  }
                />
                {errors.fullName ? <p className="mt-1 text-xs text-red-500">{errors.fullName}</p> : null}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Email</label>
                <input
                  className="input-base"
                  type="email"
                  value={form.personal.email}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, personal: { ...prev.personal, email: event.target.value } }))
                  }
                />
                {errors.email ? <p className="mt-1 text-xs text-red-500">{errors.email}</p> : null}
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Phone</label>
                <input
                  className="input-base"
                  value={form.personal.phone}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, personal: { ...prev.personal, phone: event.target.value } }))
                  }
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Location</label>
                <input
                  className="input-base"
                  value={form.personal.location}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, personal: { ...prev.personal, location: event.target.value } }))
                  }
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">LinkedIn URL</label>
                <input
                  className="input-base"
                  value={form.personal.linkedin}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, personal: { ...prev.personal, linkedin: event.target.value } }))
                  }
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Portfolio URL</label>
                <input
                  className="input-base"
                  value={form.personal.portfolio}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, personal: { ...prev.personal, portfolio: event.target.value } }))
                  }
                />
              </div>
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">Professional Summary</label>
                <button type="button" className="btn-secondary" onClick={handleGenerateSummary}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  AI Generate
                </button>
              </div>
              <textarea
                rows={5}
                className="input-base"
                value={form.personal.summary}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, personal: { ...prev.personal, summary: event.target.value } }))
                }
              />
            </div>
          </section>
        ) : null}

        {step === 2 ? (
          <section className="surface-card space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Step 2 — Work Experience</h2>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setForm((prev) => ({ ...prev, experience: [...prev.experience, { ...EMPTY_EXPERIENCE }] }))}
              >
                Add Experience
              </button>
            </div>
            {errors.experience ? <p className="text-xs text-red-500">{errors.experience}</p> : null}

            <div className="space-y-4">
              {form.experience.map((item, index) => (
                <div key={index} className="rounded-xl border border-gray-200 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-sm font-semibold text-gray-800">Experience #{index + 1}</p>
                    <div className="flex gap-2">
                      <button type="button" className="btn-secondary" onClick={() => aiEnhanceExperience(index)}>
                        AI Enhance
                      </button>
                      {form.experience.length > 1 ? (
                        <button
                          type="button"
                          className="btn-danger"
                          onClick={() =>
                            setForm((prev) => ({
                              ...prev,
                              experience: prev.experience.filter((_, idx) => idx !== index),
                            }))
                          }
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <input
                      className="input-base"
                      placeholder="Job Title"
                      value={item.title}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.experience];
                          next[index] = { ...next[index], title: event.target.value };
                          return { ...prev, experience: next };
                        })
                      }
                    />
                    <input
                      className="input-base"
                      placeholder="Company"
                      value={item.company}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.experience];
                          next[index] = { ...next[index], company: event.target.value };
                          return { ...prev, experience: next };
                        })
                      }
                    />
                    <input
                      className="input-base"
                      placeholder="Location"
                      value={item.location}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.experience];
                          next[index] = { ...next[index], location: event.target.value };
                          return { ...prev, experience: next };
                        })
                      }
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        className="input-base"
                        type="month"
                        value={item.start_date}
                        onChange={(event) =>
                          setForm((prev) => {
                            const next = [...prev.experience];
                            next[index] = { ...next[index], start_date: event.target.value };
                            return { ...prev, experience: next };
                          })
                        }
                      />
                      <input
                        className="input-base"
                        type="month"
                        value={item.end_date}
                        disabled={item.current}
                        onChange={(event) =>
                          setForm((prev) => {
                            const next = [...prev.experience];
                            next[index] = { ...next[index], end_date: event.target.value };
                            return { ...prev, experience: next };
                          })
                        }
                      />
                    </div>
                  </div>

                  <label className="mt-3 flex items-center gap-2 text-sm text-gray-600">
                    <input
                      type="checkbox"
                      checked={item.current}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.experience];
                          next[index] = { ...next[index], current: event.target.checked };
                          return { ...prev, experience: next };
                        })
                      }
                    />
                    Currently working here
                  </label>

                  <textarea
                    rows={4}
                    className="input-base mt-3"
                    placeholder="Describe impact, achievements, and responsibilities..."
                    value={item.description}
                    onChange={(event) =>
                      setForm((prev) => {
                        const next = [...prev.experience];
                        next[index] = { ...next[index], description: event.target.value };
                        return { ...prev, experience: next };
                      })
                    }
                  />
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {step === 3 ? (
          <section className="surface-card space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Step 3 — Education</h2>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setForm((prev) => ({ ...prev, education: [...prev.education, { ...EMPTY_EDUCATION }] }))}
              >
                Add Education
              </button>
            </div>
            {errors.education ? <p className="text-xs text-red-500">{errors.education}</p> : null}
            <div className="space-y-4">
              {form.education.map((item, index) => (
                <div key={index} className="rounded-xl border border-gray-200 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-sm font-semibold text-gray-800">Education #{index + 1}</p>
                    {form.education.length > 1 ? (
                      <button
                        type="button"
                        className="btn-danger"
                        onClick={() =>
                          setForm((prev) => ({
                            ...prev,
                            education: prev.education.filter((_, idx) => idx !== index),
                          }))
                        }
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <input
                      className="input-base"
                      placeholder="Degree"
                      value={item.degree}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.education];
                          next[index] = { ...next[index], degree: event.target.value };
                          return { ...prev, education: next };
                        })
                      }
                    />
                    <input
                      className="input-base"
                      placeholder="Institution"
                      value={item.institution}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.education];
                          next[index] = { ...next[index], institution: event.target.value };
                          return { ...prev, education: next };
                        })
                      }
                    />
                    <input
                      className="input-base"
                      placeholder="Field of Study"
                      value={item.field}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.education];
                          next[index] = { ...next[index], field: event.target.value };
                          return { ...prev, education: next };
                        })
                      }
                    />
                    <input
                      className="input-base"
                      placeholder="Grade / CGPA"
                      value={item.gpa}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.education];
                          next[index] = { ...next[index], gpa: event.target.value };
                          return { ...prev, education: next };
                        })
                      }
                    />
                    <input
                      className="input-base"
                      placeholder="Start Year"
                      value={item.start_year}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.education];
                          next[index] = { ...next[index], start_year: event.target.value };
                          return { ...prev, education: next };
                        })
                      }
                    />
                    <input
                      className="input-base"
                      placeholder="End Year"
                      value={item.end_year}
                      onChange={(event) =>
                        setForm((prev) => {
                          const next = [...prev.education];
                          next[index] = { ...next[index], end_year: event.target.value };
                          return { ...prev, education: next };
                        })
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {step === 4 ? (
          <section className="surface-card space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Step 4 — Skills</h2>
            {errors.skills ? <p className="text-xs text-red-500">{errors.skills}</p> : null}

            <TagInput
              label="Technical Skills"
              values={form.skills.technical}
              onChange={(next) => setForm((prev) => ({ ...prev, skills: { ...prev.skills, technical: next } }))}
              placeholder="Type a skill and press Enter"
            />

            {suggestedSkills.length ? (
              <div>
                <p className="mb-2 text-sm font-medium text-gray-700">Suggested Skills</p>
                <div className="flex flex-wrap gap-2">
                  {suggestedSkills.map((skill) => (
                    <button
                      key={skill}
                      type="button"
                      className="rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-700 hover:bg-teal-100"
                      onClick={() => {
                        if (form.skills.technical.includes(skill)) return;
                        setForm((prev) => ({
                          ...prev,
                          skills: { ...prev.skills, technical: [...prev.skills.technical, skill] },
                        }));
                      }}
                    >
                      + {skill}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <TagInput
              label="Languages"
              values={form.skills.languages}
              onChange={(next) => setForm((prev) => ({ ...prev, skills: { ...prev.skills, languages: next } }))}
              placeholder="Type a language and press Enter"
            />

            <TagInput
              label="Certifications"
              values={form.skills.certifications}
              onChange={(next) => setForm((prev) => ({ ...prev, skills: { ...prev.skills, certifications: next } }))}
              placeholder="Type a certification and press Enter"
            />
          </section>
        ) : null}

        {step === 5 ? (
          <section className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
            <div className="surface-card space-y-4">
              <h2 className="text-lg font-semibold text-gray-900">Step 5 — Template & Export</h2>

              <div className="rounded-xl border border-gray-200 bg-white p-3">
                <p className="text-sm font-semibold text-gray-900">Import LaTeX template from web</p>
                <div className="mt-2 grid gap-2 md:grid-cols-[1fr,220px,auto]">
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
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={importTemplateFromWeb}
                    disabled={importingTemplate}
                  >
                    {importingTemplate ? "Importing..." : "Import URL"}
                  </button>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {templates.map((template, index) => {
                  const active = form.templateId === template.id;
                  return (
                    <button
                      type="button"
                      key={template.id}
                      className={`rounded-xl border p-3 text-left ${
                        active ? "border-teal-500 bg-teal-50" : "border-gray-200 bg-white hover:border-teal-300"
                      }`}
                      onClick={() => setForm((prev) => ({ ...prev, templateId: template.id }))}
                    >
                      <div className="mb-3 h-24 overflow-hidden rounded-lg border border-gray-100 bg-gray-50">
                        <TemplatePreviewThumb
                          templateId={template.id}
                          previewUrl={template.preview_url}
                          heightClass="h-24"
                          fallbackClassName={`bg-gradient-to-br ${initialsTemplateClass(index)}`}
                        />
                      </div>
                      <p className="text-sm font-semibold text-gray-900">{template.name}</p>
                      <p className="text-xs text-gray-500">{template.best_for || template.style}</p>
                    </button>
                  );
                })}
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <AccentColorPicker
                  value={form.accentColor}
                  onChange={(hex) => setForm((prev) => ({ ...prev, accentColor: hex }))}
                />
              </div>

              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn-primary" onClick={() => exportResume("pdf")}>
                  Download PDF
                </button>
                <button type="button" className="btn-secondary" onClick={() => exportResume("docx")}>
                  Download DOCX
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={async () => {
                    const id = await saveResume(false);
                    if (id) navigate(`/resume/${id}/edit`);
                  }}
                >
                  Save Resume
                </button>
              </div>
            </div>

            <div className="surface-card">
              <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-gray-500">Live Preview</h3>
              <p className="mb-3 text-xs text-gray-500">
                Reflects your draft + selected ATS template and accent color.
              </p>
              <AnimatedResumePreview
                key={`${form.templateId}-${form.accentColor}`}
                template={templates.find((t) => t.id === form.templateId)}
                templateId={form.templateId}
                resume={mapToParsedJson(form)}
                accentColor={normalizeAccentHex(form.accentColor)}
                className="rounded-xl border border-gray-100 bg-slate-50/80 p-2"
              />
              <a
                href="https://word.cloud.microsoft/search/ats/?wdOrigin=SEO-INTENT.WD-SE-L46-1-L46-1.SEARCHTEMPLATES"
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-block text-xs font-medium text-teal-600 hover:text-teal-700"
              >
                Microsoft Word ATS template gallery
              </a>
            </div>
          </section>
        ) : null}

        <div className="flex items-center justify-between gap-3">
          <button type="button" className="btn-secondary" onClick={handlePrevious} disabled={step === 1}>
            Previous
          </button>
          <button type="button" className="btn-primary" onClick={handleNext} disabled={step === 5}>
            Next
          </button>
        </div>
      </div>
    </>
  );
}


