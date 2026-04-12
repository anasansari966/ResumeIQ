import { useEffect, useState, useCallback, useMemo } from "react";
import { api } from "../api.js";

function emptyDraft() {
  return {
    contact: { name: "", email: "", phone: "", linkedin: "", github: "", location: "" },
    summary: "",
    summary_origin: "model",
    experience: [],
    education: [],
    skills: { technical: [], soft: [], tools: [], certifications: [] },
    projects: [],
    languages: [],
    publications: [],
    awards: [],
    leadership: [],
    extracurricular: [],
  };
}

function lines(s) {
  return String(s || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

/** Payload sent to PATCH / generate-summary (no UI-only _* keys). */
export function buildResumePayload(draft) {
  const technical =
    draft._techText !== undefined ? lines(draft._techText) : [...(draft.skills?.technical || [])];
  const soft = draft._softText !== undefined ? lines(draft._softText) : [...(draft.skills?.soft || [])];
  const tools = draft._toolsText !== undefined ? lines(draft._toolsText) : [...(draft.skills?.tools || [])];
  const certifications =
    draft._certText !== undefined ? lines(draft._certText) : [...(draft.skills?.certifications || [])];
  const awards = draft._awardsText !== undefined ? lines(draft._awardsText) : [...(draft.awards || [])];
  const publications =
    draft._pubText !== undefined ? lines(draft._pubText) : [...(draft.publications || [])];
  const leadership =
    draft._leadText !== undefined ? lines(draft._leadText) : [...(draft.leadership || [])];
  const extracurricular =
    draft._extraText !== undefined ? lines(draft._extraText) : [...(draft.extracurricular || [])];
  const languages = draft._langText !== undefined ? lines(draft._langText) : [...(draft.languages || [])];

  const {
    _techText,
    _softText,
    _toolsText,
    _certText,
    _awardsText,
    _pubText,
    _leadText,
    _extraText,
    _langText,
    ...clean
  } = draft;

  return {
    ...clean,
    contact: {
      name: draft.contact?.name || "",
      email: draft.contact?.email || "",
      phone: draft.contact?.phone || "",
      linkedin: draft.contact?.linkedin || "",
      github: draft.contact?.github || "",
      location: draft.contact?.location || "",
    },
    summary_origin: draft.summary_origin === "document" ? "document" : "model",
    experience: (draft.experience || []).map((e) => ({
      company: e.company || "",
      title: e.title || "",
      start_date: e.start_date || "",
      end_date: e.end_date || "",
      description: Array.isArray(e.description) ? e.description : [],
      bullets: Array.isArray(e.bullets) ? e.bullets : lines(String(e.bullets || "")),
    })),
    education: (draft.education || []).map((ed) => ({
      institution: ed.institution || "",
      degree: ed.degree || "",
      field: ed.field || "",
      year: ed.year || "",
      gpa: ed.gpa != null && String(ed.gpa).trim() ? String(ed.gpa).trim() : null,
    })),
    skills: { technical, soft, tools, certifications },
    projects: (draft.projects || []).map((p) => {
      let ts = p.tech_stack;
      if (typeof ts === "string") {
        ts = ts
          .split(/[,;\n]/)
          .map((x) => x.trim())
          .filter(Boolean);
      }
      return {
        name: p.name || "",
        description: p.description || "",
        tech_stack: Array.isArray(ts) ? ts : [],
        link: p.link || null,
      };
    }),
    languages,
    publications,
    awards,
    leadership,
    extracurricular,
  };
}

export default function ResumeStructureEditor({ resume, onSaved, title = "Structured resume data" }) {
  const [draft, setDraft] = useState(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [err, setErr] = useState("");

  const parsedSig = useMemo(
    () => `${resume?.id ?? ""}\0${JSON.stringify(resume?.parsed_json ?? null)}`,
    [resume?.id, resume?.parsed_json],
  );

  useEffect(() => {
    if (!resume?.parsed_json) {
      setDraft(emptyDraft());
      return;
    }
    setDraft(JSON.parse(JSON.stringify(resume.parsed_json)));
  }, [parsedSig, resume]);

  const updateExp = useCallback((i, field, value) => {
    setDraft((d) => {
      const exp = [...(d.experience || [])];
      while (exp.length <= i) exp.push({ company: "", title: "", bullets: [], start_date: "", end_date: "" });
      exp[i] = { ...exp[i], [field]: value };
      return { ...d, experience: exp };
    });
  }, []);

  const updateEdu = useCallback((i, field, value) => {
    setDraft((d) => {
      const edu = [...(d.education || [])];
      while (edu.length <= i) edu.push({ institution: "", degree: "", field: "", year: "", gpa: "" });
      edu[i] = { ...edu[i], [field]: value };
      return { ...d, education: edu };
    });
  }, []);

  const updateProj = useCallback((i, field, value) => {
    setDraft((d) => {
      const pj = [...(d.projects || [])];
      while (pj.length <= i) pj.push({ name: "", description: "", tech_stack: [] });
      pj[i] = { ...pj[i], [field]: value };
      return { ...d, projects: pj };
    });
  }, []);

  async function save() {
    if (!resume?.id) return;
    setErr("");
    setSaving(true);
    try {
      const body = buildResumePayload(draft);
      const filteredProjects = body.projects.filter((p) => (p.name || "").trim() || (p.description || "").trim());
      await api(`/api/v1/resumes/${resume.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parsed_json: { ...body, projects: filteredProjects }, recalc_ats: true }),
      });
      onSaved?.();
    } catch (e) {
      setErr(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function generateSummary() {
    if (!resume?.id) return;
    setErr("");
    setGenLoading(true);
    try {
      const body = buildResumePayload(draft);
      const out = await api(`/api/v1/resumes/${resume.id}/generate-summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parsed_json: body }),
      });
      setDraft(JSON.parse(JSON.stringify(out.parsed_json)));
      onSaved?.();
    } catch (e) {
      setErr(e.message || "Summary generation failed");
    } finally {
      setGenLoading(false);
    }
  }

  const exp = draft.experience?.length ? draft.experience : [{ company: "", title: "", bullets: [], start_date: "", end_date: "" }];
  const edu = draft.education?.length ? draft.education : [{ institution: "", degree: "", field: "", year: "", gpa: "" }];
  const proj = draft.projects?.length ? draft.projects : [];

  const techText = draft._techText !== undefined ? draft._techText : (draft.skills?.technical || []).join("\n");
  const softText = draft._softText !== undefined ? draft._softText : (draft.skills?.soft || []).join("\n");
  const toolsText = draft._toolsText !== undefined ? draft._toolsText : (draft.skills?.tools || []).join("\n");
  const certText = draft._certText !== undefined ? draft._certText : (draft.skills?.certifications || []).join("\n");
  const awardsText = draft._awardsText !== undefined ? draft._awardsText : (draft.awards || []).join("\n");
  const pubText = draft._pubText !== undefined ? draft._pubText : (draft.publications || []).join("\n");
  const leadText = draft._leadText !== undefined ? draft._leadText : (draft.leadership || []).join("\n");
  const extraText = draft._extraText !== undefined ? draft._extraText : (draft.extracurricular || []).join("\n");
  const langText = draft._langText !== undefined ? draft._langText : (draft.languages || []).join("\n");

  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-4 space-y-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-white">{title}</h3>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={generateSummary}
            disabled={genLoading || !resume?.id}
            className="px-3 py-1.5 rounded-lg border border-violet-500/40 bg-violet-950/50 text-violet-200 text-xs font-medium disabled:opacity-50 hover:bg-violet-900/40"
          >
            {genLoading ? "Generating…" : "Generate summary (AI)"}
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving || !resume?.id}
            className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-indigo-600 text-white text-xs font-medium disabled:opacity-50 shadow-md"
          >
            {saving ? "Saving…" : "Save edits"}
          </button>
        </div>
      </div>
      <p className="text-xs text-slate-400">
        Fix extraction issues here. AI summary uses only the fields below (2–3 lines). Save persists to your resume and baseline ATS.
      </p>
      {err && <p className="text-xs text-red-400">{err}</p>}

      <div className="rounded-lg border border-white/10 bg-slate-950/50 p-3 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase">1 · Contact</p>
        <div className="grid sm:grid-cols-2 gap-2">
          <input
            placeholder="Full name"
            className="w-full input-dark-inline"
            value={draft.contact?.name || ""}
            onChange={(e) => setDraft((d) => ({ ...d, contact: { ...d.contact, name: e.target.value } }))}
          />
          <input
            placeholder="Phone"
            className="w-full input-dark-inline"
            value={draft.contact?.phone || ""}
            onChange={(e) => setDraft((d) => ({ ...d, contact: { ...d.contact, phone: e.target.value } }))}
          />
          <input
            placeholder="Email"
            className="w-full input-dark-inline"
            value={draft.contact?.email || ""}
            onChange={(e) => setDraft((d) => ({ ...d, contact: { ...d.contact, email: e.target.value } }))}
          />
          <input
            placeholder="Location"
            className="w-full input-dark-inline"
            value={draft.contact?.location || ""}
            onChange={(e) => setDraft((d) => ({ ...d, contact: { ...d.contact, location: e.target.value } }))}
          />
          <input
            placeholder="LinkedIn URL"
            className="w-full input-dark-inline sm:col-span-1"
            value={draft.contact?.linkedin || ""}
            onChange={(e) => setDraft((d) => ({ ...d, contact: { ...d.contact, linkedin: e.target.value } }))}
          />
          <input
            placeholder="GitHub URL"
            className="w-full input-dark-inline sm:col-span-1"
            value={draft.contact?.github || ""}
            onChange={(e) => setDraft((d) => ({ ...d, contact: { ...d.contact, github: e.target.value } }))}
          />
        </div>
      </div>

      <div className="rounded-lg border border-white/10 bg-slate-950/50 p-3 space-y-2">
        <p className="text-xs font-bold text-slate-500 uppercase">2 · Summary / objective</p>
        <textarea
          className="mt-1 w-full input-dark-inline min-h-[88px] text-sm"
          placeholder="Optional — use “Generate summary (AI)” from your fields, or write your own."
          value={draft.summary || ""}
          onChange={(e) => setDraft((d) => ({ ...d, summary: e.target.value }))}
        />
      </div>

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-bold text-slate-500 uppercase">3 · Experience / internships</p>
        <button
          type="button"
          className="text-xs font-medium text-cyan-300 hover:underline"
          onClick={() =>
            setDraft((d) => ({
              ...d,
              experience: [...(d.experience?.length ? d.experience : []), { company: "", title: "", bullets: [], start_date: "", end_date: "" }],
            }))
          }
        >
          + Add role
        </button>
      </div>
      {exp.map((e, i) => (
        <div key={i} className="border border-white/10 rounded-lg p-3 bg-slate-950/50 space-y-2">
          <p className="text-xs font-bold text-slate-400">Role {i + 1}</p>
          <div className="grid sm:grid-cols-2 gap-2">
            <input
              placeholder="Company"
              className="w-full input-dark-inline"
              value={e.company || ""}
              onChange={(ev) => updateExp(i, "company", ev.target.value)}
            />
            <input
              placeholder="Role / title"
              className="w-full input-dark-inline"
              value={e.title || ""}
              onChange={(ev) => updateExp(i, "title", ev.target.value)}
            />
            <input
              placeholder="Start date"
              className="w-full input-dark-inline"
              value={e.start_date || ""}
              onChange={(ev) => updateExp(i, "start_date", ev.target.value)}
            />
            <input
              placeholder="End date"
              className="w-full input-dark-inline"
              value={e.end_date || ""}
              onChange={(ev) => updateExp(i, "end_date", ev.target.value)}
            />
          </div>
          <label className="block">
            <span className="text-xs text-slate-400">Work & achievements (one bullet per line)</span>
            <textarea
              className="mt-1 w-full input-dark-inline min-h-[100px] font-mono text-xs"
              value={(e.bullets || []).join("\n")}
              onChange={(ev) =>
                updateExp(i, "bullets", ev.target.value.split("\n").map((l) => l.trim()).filter(Boolean))
              }
            />
          </label>
        </div>
      ))}

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-bold text-slate-500 uppercase">4 · Education</p>
        <button
          type="button"
          className="text-xs font-medium text-cyan-300 hover:underline"
          onClick={() =>
            setDraft((d) => ({
              ...d,
              education: [...(d.education?.length ? d.education : []), { institution: "", degree: "", field: "", year: "", gpa: "" }],
            }))
          }
        >
          + Add education
        </button>
      </div>
      {edu.map((ed, i) => (
        <div key={i} className="border border-white/10 rounded-lg p-3 bg-slate-950/50 space-y-2">
          <p className="text-xs font-bold text-slate-400">School {i + 1}</p>
          <div className="grid sm:grid-cols-2 gap-2">
            <input
              placeholder="Degree"
              className="w-full input-dark-inline"
              value={ed.degree || ""}
              onChange={(ev) => updateEdu(i, "degree", ev.target.value)}
            />
            <input
              placeholder="College / school"
              className="w-full input-dark-inline"
              value={ed.institution || ""}
              onChange={(ev) => updateEdu(i, "institution", ev.target.value)}
            />
            <input
              placeholder="Field / major"
              className="w-full input-dark-inline"
              value={ed.field || ""}
              onChange={(ev) => updateEdu(i, "field", ev.target.value)}
            />
            <input
              placeholder="Year"
              className="w-full input-dark-inline"
              value={ed.year || ""}
              onChange={(ev) => updateEdu(i, "year", ev.target.value)}
            />
            <input
              placeholder="GPA / %"
              className="w-full input-dark-inline sm:col-span-2"
              value={ed.gpa ?? ""}
              onChange={(ev) => updateEdu(i, "gpa", ev.target.value)}
            />
          </div>
        </div>
      ))}

      <div className="rounded-lg border border-white/10 bg-slate-950/50 p-3 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase">5 · Skills</p>
        <label className="block">
          <span className="text-xs font-medium text-slate-300">Technical (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[64px] font-mono text-xs"
            value={techText}
            onChange={(e) => setDraft((d) => ({ ...d, _techText: e.target.value }))}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-300">Tools / technologies (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[56px] font-mono text-xs"
            value={toolsText}
            onChange={(e) => setDraft((d) => ({ ...d, _toolsText: e.target.value }))}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-300">Soft skills (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[56px] font-mono text-xs"
            value={softText}
            onChange={(e) => setDraft((d) => ({ ...d, _softText: e.target.value }))}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-300">Certifications (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[56px] font-mono text-xs"
            value={certText}
            onChange={(e) => setDraft((d) => ({ ...d, _certText: e.target.value }))}
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-slate-300">Languages (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[48px] font-mono text-xs"
            value={langText}
            onChange={(e) => setDraft((d) => ({ ...d, _langText: e.target.value }))}
          />
        </label>
      </div>

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-bold text-slate-500 uppercase">6 · Projects</p>
        <button
          type="button"
          className="text-xs font-medium text-cyan-300 hover:underline"
          onClick={() =>
            setDraft((d) => ({
              ...d,
              projects: [...(d.projects || []), { name: "", description: "", tech_stack: [] }],
            }))
          }
        >
          + Add project
        </button>
      </div>
      <div className="space-y-2">
        {(proj.length ? proj : [{ name: "", description: "", tech_stack: [] }]).map((p, i) => (
          <div key={i} className="border border-white/10 rounded-lg p-2 bg-slate-950/50 space-y-2">
            <input
              placeholder="Project name"
              className="w-full input-dark-inline text-sm"
              value={p.name || ""}
              onChange={(ev) => updateProj(i, "name", ev.target.value)}
            />
            <textarea
              placeholder="Description"
              className="w-full input-dark-inline text-xs min-h-[48px]"
              value={p.description || ""}
              onChange={(ev) => updateProj(i, "description", ev.target.value)}
            />
            <label className="block">
              <span className="text-xs text-slate-400">Tech used (comma or newline separated)</span>
              <textarea
                className="mt-1 w-full input-dark-inline text-xs min-h-[40px] font-mono"
                value={Array.isArray(p.tech_stack) ? p.tech_stack.join(", ") : p.tech_stack || ""}
                onChange={(ev) => updateProj(i, "tech_stack", ev.target.value)}
              />
            </label>
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-white/10 bg-slate-950/50 p-3 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase">7 · Achievements / awards</p>
        <label className="block">
          <span className="text-xs text-slate-400">Competitions, certifications, recognitions (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[72px] font-mono text-xs"
            value={awardsText}
            onChange={(e) => setDraft((d) => ({ ...d, _awardsText: e.target.value }))}
          />
        </label>
      </div>

      <div className="rounded-lg border border-white/10 bg-slate-950/50 p-3 space-y-3">
        <p className="text-xs font-bold text-slate-500 uppercase">8 · Additional</p>
        <label className="block">
          <span className="text-xs text-slate-400">Positions of responsibility (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[56px] font-mono text-xs"
            value={leadText}
            onChange={(e) => setDraft((d) => ({ ...d, _leadText: e.target.value }))}
          />
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">Extracurricular (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[56px] font-mono text-xs"
            value={extraText}
            onChange={(e) => setDraft((d) => ({ ...d, _extraText: e.target.value }))}
          />
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">Publications (one per line)</span>
          <textarea
            className="mt-1 w-full input-dark-inline min-h-[56px] font-mono text-xs"
            value={pubText}
            onChange={(e) => setDraft((d) => ({ ...d, _pubText: e.target.value }))}
          />
        </label>
      </div>
    </div>
  );
}
