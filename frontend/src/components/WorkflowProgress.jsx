const STATUS_STYLES = {
  complete: {
    badge: "border-emerald-500/25 bg-emerald-500/[0.12] text-emerald-100",
    node: "border-emerald-400/60 bg-emerald-500/20 text-emerald-100 shadow-[0_0_0_4px_rgba(16,185,129,0.14)]",
    connector: "bg-emerald-400/60",
    eyebrow: "text-emerald-200/80",
  },
  current: {
    badge: "border-cyan-500/25 bg-cyan-500/[0.12] text-cyan-100",
    node: "border-cyan-400/70 bg-cyan-500/20 text-cyan-100 shadow-[0_0_0_4px_rgba(6,182,212,0.18)]",
    connector: "bg-cyan-400/55",
    eyebrow: "text-cyan-200/80",
  },
  pending: {
    badge: "border-white/10 bg-white/[0.06] text-slate-200",
    node: "border-slate-400/35 bg-slate-800/50 text-slate-200",
    connector: "bg-slate-500/45",
    eyebrow: "text-slate-400",
  },
  locked: {
    badge: "border-white/10 bg-black/20 text-slate-500",
    node: "border-white/10 bg-black/35 text-slate-500",
    connector: "bg-slate-700/70",
    eyebrow: "text-slate-500",
  },
};

const STATUS_LABELS = {
  complete: "Complete",
  current: "Current",
  pending: "Up next",
  locked: "Locked",
};

export default function WorkflowProgress({ eyebrow = "Workflow", title, description, steps, className = "" }) {
  return (
    <section className={`panel overflow-hidden border border-white/10 bg-slate-950/55 p-5 sm:p-6 ${className}`}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-400/80">{eyebrow}</p>
          <h2 className="font-display mt-2 text-xl font-bold text-white">{title}</h2>
        </div>
        {description ? <p className="max-w-2xl text-sm leading-relaxed text-slate-400">{description}</p> : null}
      </div>

      <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/45 p-4 sm:p-5">
        <div className="overflow-x-auto pb-1">
          <ol className="flex min-w-[760px] items-start gap-0 md:min-w-0">
            {steps.map((step, idx) => {
              const tone = STATUS_STYLES[step.status] || STATUS_STYLES.pending;
              const statusLabel = STATUS_LABELS[step.status] || STATUS_LABELS.pending;
              const stepNumber = step.number || idx + 1;
              return (
                <li key={step.key || step.title || idx} className="relative flex flex-1 flex-col pr-4 last:pr-0">
                  <div className="mb-2 min-h-[24px]">
                    <span
                      className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${tone.badge}`}
                    >
                      {statusLabel}
                    </span>
                  </div>
                  {idx < steps.length - 1 ? (
                    <span className={`absolute left-12 right-0 top-[2.95rem] h-[2px] rounded-full ${tone.connector}`} aria-hidden />
                  ) : null}
                  <div className="relative z-10 flex items-center">
                    <span
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-sm font-semibold ${tone.node}`}
                    >
                      {stepNumber}
                    </span>
                  </div>
                  <p className={`mt-3 text-[10px] font-semibold uppercase tracking-[0.2em] ${tone.eyebrow}`}>Step {stepNumber}</p>
                  <h3 className="mt-1 text-sm font-semibold text-white">{step.title}</h3>
                  <p className="mt-2 pr-2 text-xs leading-relaxed text-slate-400">{step.description}</p>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
