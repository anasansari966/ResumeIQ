import { useMemo } from "react";

const STAGE_LABELS = {
  saved: "Saved",
  applied: "Applied",
  phone_screen: "Phone screen",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  archived: "Archived",
};

/** Hex stops for conic-gradient (automated donut). */
const STAGE_HEX = {
  saved: "#64748b",
  applied: "#06b6d4",
  phone_screen: "#38bdf8",
  interview: "#a78bfa",
  offer: "#34d399",
  rejected: "#fb7185",
  archived: "#475569",
};

function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

/** Build 8 week buckets ending this week; count updates per app in each bucket. */
function weeklyActivitySeries(apps) {
  const end = startOfDay(new Date());
  const start = new Date(end);
  start.setDate(start.getDate() - 7 * 7);

  const buckets = Array.from({ length: 8 }, (_, i) => {
    const ws = new Date(start);
    ws.setDate(ws.getDate() + i * 7);
    const we = new Date(ws);
    we.setDate(we.getDate() + 6);
    return { ws: ws.getTime(), we: we.getTime(), count: 0, label: "" };
  });

  for (const b of buckets) {
    const d = new Date(b.ws);
    b.label = `${d.getMonth() + 1}/${d.getDate()}`;
  }

  for (const a of apps) {
    const raw = a.updated_at || a.applied_at;
    if (!raw) continue;
    const t = new Date(raw).getTime();
    if (Number.isNaN(t)) continue;
    for (const b of buckets) {
      if (t >= b.ws && t <= b.we) {
        b.count += 1;
        break;
      }
    }
  }

  return buckets;
}

function autoInsight(total, byStatus, activePipeline, offerCount) {
  if (total === 0) return "";
  const parts = [];
  const activePct = Math.round((activePipeline / total) * 100);
  parts.push(`${activePct}% of roles are still active (${activePipeline} of ${total}).`);

  let topStage = "";
  let topN = -1;
  for (const [k, v] of Object.entries(byStatus)) {
    if (v > topN) {
      topN = v;
      topStage = k;
    }
  }
  if (topStage && topN > 0) {
    const label = STAGE_LABELS[topStage] || topStage;
    parts.push(`Largest group: ${label} (${topN}).`);
  }
  if (offerCount > 0) {
    parts.push(`${offerCount} offer${offerCount === 1 ? "" : "s"} — keep momentum on follow-ups.`);
  } else if ((byStatus.interview || 0) + (byStatus.phone_screen || 0) > 0) {
    parts.push("You have interviews or screens in flight.");
  }

  return parts.join(" ");
}

export default function TrackerAnalytics({ apps, stages }) {
  const {
    total,
    activePipeline,
    offerCount,
    byStatus,
    donutGradient,
    legendItems,
    weekly,
    maxWeek,
    insight,
    svgSpark,
  } = useMemo(() => {
    const byStatus = Object.fromEntries(stages.map((s) => [s, 0]));
    for (const a of apps) {
      const s = a.status;
      if (s in byStatus) byStatus[s] += 1;
    }
    const total = apps.length;
    const offerCount = byStatus.offer || 0;
    const activePipeline = total - (byStatus.archived || 0) - (byStatus.rejected || 0);

    let fromDeg = 0;
    const gradientParts = [];
    const legendItems = [];
    if (total > 0) {
      for (const s of stages) {
        const n = byStatus[s] || 0;
        if (!n) continue;
        const sweep = (n / total) * 360;
        const color = STAGE_HEX[s] || "#94a3b8";
        const toDeg = fromDeg + sweep;
        gradientParts.push(`${color} ${fromDeg}deg ${toDeg}deg`);
        fromDeg = toDeg;
        legendItems.push({
          stage: s,
          label: STAGE_LABELS[s] || s,
          n,
          pct: Math.round((n / total) * 100),
          color,
        });
      }
    }

    const donutGradient =
      gradientParts.length > 0 ? gradientParts.join(", ") : "#334155 0deg 360deg";

    const weekly = weeklyActivitySeries(apps);
    const maxWeek = Math.max(1, ...weekly.map((b) => b.count));

    const insight = autoInsight(total, byStatus, activePipeline, offerCount);

    const w = 280;
    const h = 96;
    const pad = 8;
    const innerH = h - 2 * pad;
    const pts = weekly.map((b, i) => {
      const x = pad + (i * (w - 2 * pad)) / Math.max(1, weekly.length - 1);
      const y = h - pad - (b.count / maxWeek) * innerH;
      return `${x},${y}`;
    });
    const svgSpark = pts.length > 0 ? pts.join(" ") : "";

    return {
      total,
      activePipeline,
      offerCount,
      byStatus,
      donutGradient,
      legendItems,
      weekly,
      maxWeek,
      insight,
      svgSpark,
    };
  }, [apps, stages]);

  if (total === 0) {
    return (
      <div className="panel p-6 border-dashed border-white/20">
        <h2 className="text-sm font-semibold text-white">Automated pipeline view</h2>
        <p className="mt-2 text-sm text-slate-500">
          Save or apply to jobs from <span className="text-slate-400">Job search</span> to generate your stage mix and
          activity trend.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="panel p-4 border border-white/10 bg-slate-950/50">
        <p className="text-[10px] font-bold uppercase tracking-wider text-cyan-400/80">Auto summary</p>
        <p className="mt-2 text-sm text-slate-200 leading-relaxed">{insight}</p>
        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
          <div>
            <dt className="inline text-slate-600">Tracked</dt>{" "}
            <dd className="inline font-semibold text-slate-300 tabular-nums">{total}</dd>
          </div>
          <div>
            <dt className="inline text-slate-600">Active</dt>{" "}
            <dd className="inline font-semibold text-cyan-200/90 tabular-nums">{activePipeline}</dd>
          </div>
          <div>
            <dt className="inline text-slate-600">Offers</dt>{" "}
            <dd className="inline font-semibold text-emerald-300/90 tabular-nums">{offerCount}</dd>
          </div>
        </dl>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-5 flex flex-col">
          <h2 className="text-sm font-semibold text-white">Stage mix</h2>
          <p className="text-xs text-slate-500 mt-0.5">Share of applications in each stage (updates automatically)</p>
          <div className="mt-6 flex flex-col sm:flex-row items-center gap-6 flex-1">
            <div
              className="relative h-36 w-36 shrink-0 rounded-full shadow-lg shadow-black/40 ring-1 ring-white/10"
              style={{
                background: `conic-gradient(${donutGradient})`,
                maskImage: "radial-gradient(farthest-side, transparent 56%, black 57%)",
                WebkitMaskImage: "radial-gradient(farthest-side, transparent 56%, black 57%)",
              }}
              aria-hidden
            />
            <ul className="flex-1 space-y-2 min-w-0 w-full sm:max-h-52 sm:overflow-y-auto">
              {legendItems.map(({ stage, label, n, pct, color }) => (
                <li key={stage} className="flex items-center justify-between gap-2 text-xs">
                  <span className="flex items-center gap-2 min-w-0">
                    <span className="h-2.5 w-2.5 rounded-sm shrink-0 ring-1 ring-white/20" style={{ backgroundColor: color }} />
                    <span className="text-slate-300 truncate">{label}</span>
                  </span>
                  <span className="text-slate-500 tabular-nums shrink-0">
                    {n} <span className="text-slate-600">({pct}%)</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="panel p-5 flex flex-col">
          <h2 className="text-sm font-semibold text-white">8-week activity</h2>
          <p className="text-xs text-slate-500 mt-0.5">Application touches by week (from last update dates)</p>
          <div className="mt-4 flex-1 min-h-[7rem]">
            <svg viewBox={`0 0 280 96`} className="w-full h-24 overflow-visible" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgb(34 211 238)" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="rgb(34 211 238)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {svgSpark && (
                <>
                  <polyline
                    fill="none"
                    stroke="rgb(34 211 238)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={svgSpark}
                  />
                  <polygon
                    fill="url(#sparkFill)"
                    points={`8,88 ${svgSpark} 272,88`}
                    opacity="1"
                  />
                </>
              )}
              {weekly.map((b, i) => {
                const x = 8 + (i * (280 - 16)) / Math.max(1, weekly.length - 1);
                const cy = 88 - (b.count / maxWeek) * 80;
                return (
                  <circle
                    key={b.label + i}
                    cx={x}
                    cy={cy}
                    r={b.count ? 3.5 : 2}
                    className={b.count ? "fill-cyan-300" : "fill-slate-600"}
                  />
                );
              })}
            </svg>
            <div className="flex justify-between mt-1 px-1">
              {weekly.map((b) => (
                <span key={b.label} className="text-[9px] text-slate-600 w-8 text-center truncate">
                  {b.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
