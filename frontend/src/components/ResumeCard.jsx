import { useMemo, useState } from "react";
import { Copy, Download, Edit3, MoreVertical, Trash2 } from "lucide-react";

function atsTone(score) {
  if (score < 50) return "bg-red-100 text-red-700";
  if (score <= 75) return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

export default function ResumeCard({ resume, onEdit, onDelete, onDuplicate, onDownload }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const title = useMemo(() => {
    if (resume?.parsed_json?.contact?.name) return `${resume.parsed_json.contact.name} Resume`;
    if (resume?.file_name) return resume.file_name;
    return `Resume #${resume?.id}`;
  }, [resume]);

  const score = Math.round(Number(resume?.ats_baseline || resume?.parsed_json?.ats_score_baseline || 0));

  return (
    <article className="surface-card group hover:shadow-md">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-teal-100 to-sky-100" />
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-gray-900">{title}</h3>
            <p className="text-xs text-gray-500">
              Updated {resume?.updated_at ? new Date(resume.updated_at).toLocaleDateString() : "recently"}
            </p>
          </div>
        </div>

        <div className="relative">
          <button
            type="button"
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100"
            onClick={() => setMenuOpen((prev) => !prev)}
          >
            <MoreVertical className="h-4 w-4" />
          </button>

          {menuOpen ? (
            <div className="absolute right-0 top-10 z-10 w-40 rounded-lg border border-gray-200 bg-white p-1 shadow-md">
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                onClick={() => {
                  setMenuOpen(false);
                  onEdit?.(resume);
                }}
              >
                <Edit3 className="h-4 w-4" />
                Edit
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                onClick={() => {
                  setMenuOpen(false);
                  onDownload?.(resume);
                }}
              >
                <Download className="h-4 w-4" />
                Download PDF
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                onClick={() => {
                  setMenuOpen(false);
                  onDuplicate?.(resume);
                }}
              >
                <Copy className="h-4 w-4" />
                Duplicate
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-red-600 hover:bg-red-50"
                onClick={() => {
                  setMenuOpen(false);
                  onDelete?.(resume);
                }}
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">ATS score</span>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${atsTone(score)}`}>{score}/100</span>
      </div>
    </article>
  );
}
