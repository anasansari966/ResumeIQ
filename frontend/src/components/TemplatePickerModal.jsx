import { useEffect, useState } from "react";
import DocxTemplatePreview from "./AnimatedResumePreview.jsx";
import { templateFileTitle } from "../templateDisplayName.js";

export default function TemplatePickerModal({
  open,
  templates,
  selectedTemplateId,
  activePreviewTemplateId = "",
  resume,
  saving = false,
  onClose,
  onPreviewChange,
  onSelect,
}) {
  const [previewTemplateId, setPreviewTemplateId] = useState("");
  const usingFolderTemplates = templates.some((item) => item.source === "folder");
  const librarySummary = usingFolderTemplates
    ? `${templates.length} template${templates.length === 1 ? "" : "s"} loaded from Templates/`
    : `${templates.length} template${templates.length === 1 ? "" : "s"} available`;

  useEffect(() => {
    if (!open) return;
    setPreviewTemplateId(activePreviewTemplateId || selectedTemplateId || templates[0]?.id || "");
  }, [open, activePreviewTemplateId, selectedTemplateId, templates]);

  if (!open) return null;

  const previewTemplate =
    templates.find((item) => item.id === previewTemplateId) ||
    templates.find((item) => item.id === selectedTemplateId) ||
    templates[0] ||
    null;

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4 sm:p-6">
      <button
        type="button"
        className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
        onClick={saving ? undefined : onClose}
        aria-label="Close template picker"
      />
      <div className="relative z-10 grid max-h-[92vh] w-full max-w-6xl gap-4 overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/95 shadow-2xl shadow-black/50 lg:grid-cols-[360px,1fr]">
        <section className="border-b border-white/10 p-5 sm:p-6 lg:border-b-0 lg:border-r">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-400/85">Template picker</p>
              <h2 className="font-display mt-2 text-2xl font-bold text-white">Choose how the resume should look</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                Preview each layout, then save one as the active template before continuing with enhancement, export, or tailoring.
              </p>
              <p className="mt-2 text-xs text-slate-500">{librarySummary}</p>
            </div>
            <button
              type="button"
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white"
              onClick={saving ? undefined : onClose}
            >
              Close
            </button>
          </div>

          <div className="mt-5 space-y-3 overflow-y-auto pr-1 lg:max-h-[calc(92vh-180px)]">
            {templates.map((template) => {
              const isPreview = template.id === previewTemplate?.id;
              const isSelected = template.id === selectedTemplateId;
              return (
                <article
                  key={template.id}
                  className={`rounded-2xl border p-4 transition ${
                    isPreview
                      ? "border-cyan-400/45 bg-cyan-950/20 shadow-lg shadow-cyan-950/20"
                      : "border-white/10 bg-white/[0.03]"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-cyan-500/25 bg-cyan-950/40 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-200">
                          {(template.kind || "template").replace(/_/g, " ")}
                        </span>
                        {isSelected && (
                          <span className="rounded-full border border-emerald-500/25 bg-emerald-950/35 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-200">
                            Active
                          </span>
                        )}
                      </div>
                      <h3 className="mt-3 text-base font-semibold text-white">{templateFileTitle(template.name)}</h3>
                      <p className="mt-1 text-sm text-slate-400">{template.best_for || template.description}</p>
                      <p className="mt-3 text-xs text-slate-500">ATS {template.ats_score} | {template.style}</p>
                    </div>
                    <div className="flex shrink-0 flex-col gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setPreviewTemplateId(template.id);
                          onPreviewChange?.(template.id);
                        }}
                        className="ghost-btn !px-3 !py-2 text-xs"
                      >
                        Preview
                      </button>
                      <button
                        type="button"
                        onClick={() => onSelect(template.id)}
                        disabled={saving}
                        className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                          isSelected
                            ? "border border-emerald-500/25 bg-emerald-500/15 text-emerald-100"
                            : "bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-lg shadow-cyan-950/30 hover:brightness-110"
                        } disabled:opacity-50`}
                      >
                        {saving && isPreview ? "Saving..." : isSelected ? "Selected" : "Use template"}
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="flex min-h-[420px] flex-col overflow-hidden">
          <div className="border-b border-white/10 px-5 py-4 sm:px-6">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Live preview</p>
            <h3 className="mt-2 text-lg font-semibold text-white">
              {previewTemplate ? templateFileTitle(previewTemplate.name) : "Select a template"}
            </h3>
            <p className="mt-1 text-sm text-slate-400">
              {previewTemplate?.best_for || "The preview updates with the current resume content."}
            </p>
          </div>
          <div className="flex-1 overflow-auto bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.08),transparent_38%),linear-gradient(180deg,#0b1020_0%,#090d17_100%)] p-4 sm:p-6">
            {previewTemplate ? (
              <div className="rounded-[24px] border border-white/10 bg-slate-950/40 p-3 shadow-2xl shadow-black/30">
                <DocxTemplatePreview
                  template={previewTemplate}
                  templateId={previewTemplate.id}
                  resume={resume}
                  className="min-h-[62vh] rounded-[18px] border-white/5 bg-white"
                />
              </div>
            ) : (
              <div className="flex h-full items-center justify-center rounded-3xl border border-dashed border-white/10 text-sm text-slate-500">
                Select a template to preview it here.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
