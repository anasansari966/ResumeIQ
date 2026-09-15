import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PanelRightOpen, Sparkles } from "lucide-react";
import api from "../api";
import AnimatedResumePreview from "../components/AnimatedResumePreview";
import AccentColorPicker from "../components/AccentColorPicker";
import useResumes from "../hooks/useResumes";
import { useToast } from "../components/Toast";
import { normalizeAccentHex } from "../theme/accentColors";

function widthClass(score) {
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
  const idx = Math.max(0, Math.min(20, Math.round(Number(score || 0) / 5)));
  return steps[idx];
}

function mapResumeToForm(resume) {
  const parsed = resume?.parsed_json || {};
  const contact = parsed.contact || {};
  const exp = Array.isArray(parsed.experience) && parsed.experience.length ? parsed.experience : [{}];
  return {
    title: contact.name ? `${contact.name} Resume` : `Resume #${resume?.id || ""}`,
    personal: {
      fullName: contact.name || "",
      email: contact.email || "",
      phone: contact.phone || "",
      location: contact.location || "",
      linkedin: contact.linkedin || "",
      portfolio: contact.portfolio || "",
    },
    summary: parsed.summary || "",
    experience: exp.map((item) => ({
      title: item.title || "",
      company: item.company || "",
      description: Array.isArray(item.bullets) ? item.bullets.join("\n") : item.description || "",
      start_date: item.start_date || "",
      end_date: item.end_date || "",
    })),
    skills: Array.isArray(parsed.skills?.technical)
      ? parsed.skills.technical.join(", ")
      : Array.isArray(parsed.skills)
        ? parsed.skills.join(", ")
        : "",
    ats: Math.round(Number(resume?.ats_baseline || parsed?.ats_score_baseline || 0)),
  };
}

function mapFormToParsed(form) {
  return {
    contact: {
      name: form.personal.fullName,
      email: form.personal.email,
      phone: form.personal.phone,
      location: form.personal.location,
      linkedin: form.personal.linkedin,
      portfolio: form.personal.portfolio,
    },
    summary: form.summary,
    ats_score_baseline: Number(form.ats) || 0,
    experience: form.experience.map((item) => ({
      title: item.title,
      company: item.company,
      start_date: item.start_date,
      end_date: item.end_date,
      bullets: item.description
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      description: item.description,
    })),
    skills: {
      technical: form.skills
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    },
  };
}

export default function ResumeEditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { getResume, updateResume, downloadResume } = useResumes();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(null);
  const [debouncedForm, setDebouncedForm] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [accentColor, setAccentColor] = useState("#0f766e");
  const [exportKind, setExportKind] = useState("pdf");
  const [atsOpen, setAtsOpen] = useState(false);
  const [atsLoading, setAtsLoading] = useState(false);
  const [atsResult, setAtsResult] = useState(null);
  const [sectionOpen, setSectionOpen] = useState({
    personal: true,
    summary: true,
    experience: true,
    skills: true,
  });

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [resume, templatesResp] = await Promise.all([
          getResume(id),
          api.get("/templates").then((r) => r.data || []),
        ]);
        const mapped = mapResumeToForm(resume);
        setForm(mapped);
        setDebouncedForm(mapped);
        setTemplateId(resume?.active_template_id || templatesResp?.[0]?.id || "");
        setAccentColor(normalizeAccentHex(resume?.parsed_json?.accent_color || "#0f766e"));
        setTemplates(templatesResp);
      } catch {
        navigate("/dashboard");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [getResume, id, navigate]);

  useEffect(() => {
    if (!form) return undefined;
    const timer = window.setTimeout(() => setDebouncedForm(form), 500);
    return () => window.clearTimeout(timer);
  }, [form]);

  const parsedJson = useMemo(
    () => (form ? { ...mapFormToParsed(form), accent_color: normalizeAccentHex(accentColor) } : {}),
    [form, accentColor],
  );

  const toggleSection = (key) => {
    setSectionOpen((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const saveChanges = async () => {
    if (!form) return;
    setSaving(true);
    try {
      await updateResume(id, parsedJson);
      showToast({ type: "success", message: "Resume saved." });
    } finally {
      setSaving(false);
    }
  };

  const applyTemplateSelection = async (nextTemplateId, nextAccent = accentColor) => {
    if (!id || !nextTemplateId) return;
    const prev = templateId;
    const prevAccent = accentColor;
    setTemplateId(nextTemplateId);
    setAccentColor(normalizeAccentHex(nextAccent));
    try {
      const { data } = await api.post(
        `/resumes/${id}/select-template`,
        {
          template_id: nextTemplateId,
          accent_color: normalizeAccentHex(nextAccent),
          restructure: nextTemplateId !== prev,
        },
        { timeout: nextTemplateId !== prev ? 300000 : 30000 },
      );
      const resolved = data?.active_template_id || nextTemplateId;
      setTemplateId(resolved);
      if (data?.parsed_json) {
        const mapped = mapResumeToForm(data);
        setForm(mapped);
        setDebouncedForm(mapped);
      }
      if (data?.parsed_json?.accent_color) {
        setAccentColor(normalizeAccentHex(data.parsed_json.accent_color));
      }
      const ats = Math.round(Number(data?.ats_baseline ?? 0));
      setForm((p) => (p ? { ...p, ats } : p));
      if (nextTemplateId !== prev) {
        showToast({ type: "success", message: "Template applied and content restructured for ATS." });
      }
    } catch (error) {
      setTemplateId(prev);
      setAccentColor(prevAccent);
      showToast({ type: "error", message: error.response?.data?.detail || "Could not apply template." });
    }
  };

  const exportResume = async () => {
    await saveChanges();
    const safe = (templateId || "export").replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 48);
    await downloadResume(id, exportKind === "pdf" ? "pdf" : "docx", templateId, `resume-${id}-${safe}`);
  };

  const checkAts = async () => {
    setAtsLoading(true);
    try {
      const response = await api.post("/ats/score", {
        resume_json: parsedJson,
      });
      setAtsResult(response.data);
      setAtsOpen(true);
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "ATS check failed." });
    } finally {
      setAtsLoading(false);
    }
  };

  if (loading || !form || !debouncedForm) {
    return (
      <>
        <div className="surface-card animate-pulse">
          <div className="h-6 w-48 rounded bg-gray-200" />
          <div className="mt-4 h-64 rounded bg-gray-100" />
        </div>
      </>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <div className="surface-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <input
              className="rounded-lg border border-gray-200 px-3 py-2 text-lg font-semibold text-gray-900"
              value={form.title}
              onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
            />

            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                ATS {form.ats}/100
              </span>
              <button type="button" className="btn-secondary" onClick={checkAts} disabled={atsLoading}>
                {atsLoading ? "Checking..." : "Check ATS"}
              </button>
              <button type="button" className="btn-primary" onClick={saveChanges} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>

              <select
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
                value={exportKind}
                onChange={(event) => setExportKind(event.target.value)}
              >
                <option value="pdf">Export PDF</option>
                <option value="docx">Export DOCX</option>
              </select>
              <button type="button" className="btn-secondary" onClick={exportResume}>
                Export
              </button>

              <button type="button" className="btn-secondary" onClick={() => setAtsOpen((prev) => !prev)}>
                <PanelRightOpen className="mr-1 h-4 w-4" /> ATS Panel
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.05fr,1.4fr]">
          <div className="space-y-4">
            <section className="surface-card">
              <div className="mb-3 flex items-center justify-between gap-2">
                <button type="button" className="text-left text-base font-semibold" onClick={() => toggleSection("personal")}>
                  Personal Info
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setForm((prev) => ({
                      ...prev,
                      personal: {
                        ...prev.personal,
                        fullName: prev.personal.fullName.trim(),
                        email: prev.personal.email.trim().toLowerCase(),
                        phone: prev.personal.phone.trim(),
                        location: prev.personal.location.trim(),
                        linkedin: prev.personal.linkedin.trim(),
                        portfolio: prev.personal.portfolio.trim(),
                      },
                    }));
                    showToast({ type: "info", message: "Personal details normalized." });
                  }}
                >
                  <Sparkles className="mr-2 h-4 w-4" /> AI Enhance
                </button>
              </div>
              {sectionOpen.personal ? (
                <div className="grid gap-3">
                  <input
                    className="input-base"
                    placeholder="Full name"
                    value={form.personal.fullName}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, personal: { ...prev.personal, fullName: event.target.value } }))
                    }
                  />
                  <input
                    className="input-base"
                    placeholder="Email"
                    value={form.personal.email}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, personal: { ...prev.personal, email: event.target.value } }))
                    }
                  />
                  <input
                    className="input-base"
                    placeholder="Phone"
                    value={form.personal.phone}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, personal: { ...prev.personal, phone: event.target.value } }))
                    }
                  />
                  <input
                    className="input-base"
                    placeholder="Location"
                    value={form.personal.location}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, personal: { ...prev.personal, location: event.target.value } }))
                    }
                  />
                  <input
                    className="input-base"
                    placeholder="LinkedIn"
                    value={form.personal.linkedin}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, personal: { ...prev.personal, linkedin: event.target.value } }))
                    }
                  />
                </div>
              ) : null}
            </section>

            <section className="surface-card">
              <div className="mb-3 flex items-center justify-between">
                <button type="button" className="text-left text-base font-semibold" onClick={() => toggleSection("summary")}>
                  Summary
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() =>
                    setForm((prev) => ({
                      ...prev,
                      summary: prev.summary
                        ? `Impact-focused profile: ${prev.summary}`
                        : "Impact-focused profile highlighting leadership, execution, and measurable outcomes.",
                    }))
                  }
                >
                  <Sparkles className="mr-2 h-4 w-4" /> AI Enhance
                </button>
              </div>
              {sectionOpen.summary ? (
                <textarea
                  rows={5}
                  className="input-base"
                  value={form.summary}
                  onChange={(event) => setForm((prev) => ({ ...prev, summary: event.target.value }))}
                />
              ) : null}
            </section>

            <section className="surface-card">
              <div className="mb-3 flex items-center justify-between">
                <button type="button" className="text-left text-base font-semibold" onClick={() => toggleSection("experience")}>
                  Experience
                </button>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() =>
                      setForm((prev) => ({
                        ...prev,
                        experience: prev.experience.map((item) => {
                          const lines = String(item.description || "")
                            .split("\n")
                            .map((line) => line.trim())
                            .filter(Boolean)
                            .map((line) => {
                              if (/^(Led|Built|Improved|Delivered)\b/.test(line)) return line;
                              return `Led ${line.charAt(0).toLowerCase()}${line.slice(1)}`;
                            });
                          return { ...item, description: lines.join("\n") };
                        }),
                      }))
                    }
                  >
                    <Sparkles className="mr-2 h-4 w-4" /> AI Enhance
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() =>
                      setForm((prev) => ({
                        ...prev,
                        experience: [
                          ...prev.experience,
                          { title: "", company: "", description: "", start_date: "", end_date: "" },
                        ],
                      }))
                    }
                  >
                    Add
                  </button>
                </div>
              </div>
              {sectionOpen.experience ? (
                <div className="space-y-3">
                  {form.experience.map((item, index) => (
                    <div key={index} className="rounded-lg border border-gray-200 p-3">
                      <input
                        className="input-base mb-2"
                        placeholder="Title"
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
                        className="input-base mb-2"
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
                      <textarea
                        rows={3}
                        className="input-base"
                        placeholder="Description"
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
              ) : null}
            </section>

            <section className="surface-card">
              <div className="mb-3 flex items-center justify-between gap-2">
                <button type="button" className="text-left text-base font-semibold" onClick={() => toggleSection("skills")}>
                  Skills
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() =>
                    setForm((prev) => ({
                      ...prev,
                      skills: prev.skills
                        .split(",")
                        .map((item) => item.trim())
                        .filter(Boolean)
                        .map((item) => item.charAt(0).toUpperCase() + item.slice(1))
                        .filter((item, index, arr) => arr.indexOf(item) === index)
                        .join(", "),
                    }))
                  }
                >
                  <Sparkles className="mr-2 h-4 w-4" /> AI Enhance
                </button>
              </div>
              {sectionOpen.skills ? (
                <textarea
                  rows={3}
                  className="input-base"
                  placeholder="Comma separated skills"
                  value={form.skills}
                  onChange={(event) => setForm((prev) => ({ ...prev, skills: event.target.value }))}
                />
              ) : null}
            </section>
          </div>

          <div className="surface-card">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-gray-900">Live Preview</h2>
                <p className="mt-0.5 text-xs text-gray-500">
                  Updates as you edit. Switch template or accent color before download.
                </p>
              </div>
              <select
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
                value={templateId}
                onChange={(event) => {
                  void applyTemplateSelection(event.target.value);
                }}
              >
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <AccentColorPicker
                value={accentColor}
                onChange={(hex) => {
                  setAccentColor(hex);
                  void applyTemplateSelection(templateId, hex);
                }}
              />
            </div>

            <AnimatedResumePreview
              key={`${templateId}-${accentColor}`}
              template={templates.find((row) => row.id === templateId) || { id: templateId, name: "Template" }}
              templateId={templateId}
              resume={{ ...mapFormToParsed(debouncedForm), accent_color: normalizeAccentHex(accentColor) }}
              accentColor={normalizeAccentHex(accentColor)}
              className="rounded-xl border border-gray-100 bg-slate-50/80 p-2"
            />

            <p className="mt-3 text-xs text-gray-500">
              PDF export uses the selected LaTeX ATS template. Edit sections on the left, then Export when ready.
            </p>
            <a
              href="https://word.cloud.microsoft/search/ats/?wdOrigin=SEO-INTENT.WD-SE-L46-1-L46-1.SEARCHTEMPLATES"
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-xs font-medium text-teal-600 hover:text-teal-700"
            >
              Browse Microsoft Word ATS template gallery (inspiration)
            </a>
          </div>
        </div>
      </div>

      {atsOpen ? (
        <div className="fixed inset-0 z-[115] flex justify-end">
          <button type="button" className="absolute inset-0 bg-black/25" onClick={() => setAtsOpen(false)} />
          <aside className="relative h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-md">
            <h3 className="text-lg font-bold text-gray-900">ATS Score Panel</h3>

            <div className="mt-4 rounded-xl border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Overall score</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{Math.round(Number(atsResult?.overall || form.ats || 0))}/100</p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-200">
                <div className={`h-full bg-teal-500 ${widthClass(atsResult?.overall || form.ats || 0)}`} />
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-gray-200 p-4">
              <p className="text-sm font-semibold text-gray-900">Section scores</p>
              <div className="mt-3 space-y-3">
                {Object.entries(atsResult?.dimensions || {}).map(([key, value]) => (
                  <div key={key}>
                    <div className="flex items-center justify-between text-xs text-gray-600">
                      <span className="capitalize">{key.replace(/_/g, " ")}</span>
                      <span>{Math.round(Number(value || 0))}</span>
                    </div>
                    <div className="mt-1 h-2 overflow-hidden rounded-full bg-gray-200">
                      <div className={`h-full bg-emerald-500 ${widthClass(value)}`} />
                    </div>
                  </div>
                ))}
                {!Object.keys(atsResult?.dimensions || {}).length ? (
                  <p className="text-sm text-gray-500">Run ATS check to see section-level scores.</p>
                ) : null}
              </div>
            </div>

            <div className="mt-4 rounded-xl border border-gray-200 p-4">
              <p className="text-sm font-semibold text-gray-900">Missing keywords list</p>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                {(atsResult?.suggestions || []).slice(0, 8).map((item, idx) => (
                  <li key={`${idx}-${item}`}>� {item}</li>
                ))}
                {!atsResult?.suggestions?.length ? <li>� No missing keywords detected yet.</li> : null}
              </ul>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

