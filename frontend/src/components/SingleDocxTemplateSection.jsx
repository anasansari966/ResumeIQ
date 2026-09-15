import DocxTemplatePreview from "./AnimatedResumePreview.jsx";
import { templateFileTitle } from "../templateDisplayName.js";

/**
 * Active resume template panel.
 */
export default function SingleDocxTemplateSection({ template, resumeId, loading }) {
  if (loading) {
    return <p className="text-sm text-slate-500">Loading template...</p>;
  }
  if (!template) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-950/30 px-4 py-3 text-sm text-amber-100/90">
        <p className="font-medium text-amber-200">Template not found</p>
        <p className="mt-1 text-amber-100/75">
          Configure at least one supported template in backend template settings and refresh.
        </p>
      </div>
    );
  }

  const title = templateFileTitle(template.name);
  const fileLabel = template.file_name || `${title}.tex`;
  const kindLabel = (template.kind || "template").toUpperCase();

  return (
    <div className="space-y-3">
      <div className="rounded-xl bg-slate-950/50 border border-white/10 px-4 py-3 flex flex-wrap items-center gap-2">
        <span className="text-[9px] font-semibold bg-gradient-to-r from-violet-600 to-teal-600 text-white px-2 py-0.5 rounded">
          {kindLabel}
        </span>
        <span className="text-sm font-semibold text-white">{title}</span>
        <span className="text-xs text-slate-400">
          <span className="font-mono">{fileLabel}</span>
        </span>
      </div>
      <div className="rounded-2xl border border-cyan-500/25 overflow-hidden bg-slate-950/40 shadow-lg shadow-black/30">
        <DocxTemplatePreview template={template} templateId={template.id} className="min-h-[360px] rounded-none border-0 shadow-none" />
      </div>
    </div>
  );
}
