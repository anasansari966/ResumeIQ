import { useEffect, useMemo, useState } from "react";
import { DragDropContext, Draggable, Droppable } from "react-beautiful-dnd";
import useApplications from "../hooks/useApplications";
import useJobs from "../hooks/useJobs";
import useResumes from "../hooks/useResumes";

const COLUMN_MAP = {
  saved: "Saved",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

const COLUMN_ORDER = ["saved", "applied", "interview", "offer", "rejected"];

const BORDER_TONE = {
  saved: "border-l-slate-400",
  applied: "border-l-teal-500",
  interview: "border-l-amber-500",
  offer: "border-l-emerald-500",
  rejected: "border-l-red-500",
};

function StrictModeDroppable({ children, ...props }) {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const raf = window.requestAnimationFrame(() => setEnabled(true));
    return () => {
      window.cancelAnimationFrame(raf);
      setEnabled(false);
    };
  }, []);

  if (!enabled) return null;
  return <Droppable {...props}>{children}</Droppable>;
}

function withinDateRange(row, fromDate, toDate) {
  const t = row.applied_at || row.updated_at;
  if (!t) return true;
  const date = new Date(t);
  if (Number.isNaN(date.getTime())) return true;
  if (fromDate && date < new Date(fromDate)) return false;
  if (toDate && date > new Date(`${toDate}T23:59:59`)) return false;
  return true;
}

export default function ApplicationsPage() {
  const { applications, loading, fetchApplications, updateApplication, setApplications } = useApplications();
  const { jobs, matchJobs } = useJobs();
  const { resumes, fetchResumes } = useResumes();

  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [selected, setSelected] = useState(null);
  const [timelineById, setTimelineById] = useState({});

  useEffect(() => {
    const load = async () => {
      const [appsData] = await Promise.all([fetchApplications(), matchJobs(), fetchResumes()]);
      const nextTimeline = {};
      for (const row of appsData) {
        nextTimeline[row.id] = [
          {
            id: `${row.id}-initial`,
            at: row.updated_at || row.applied_at || new Date().toISOString(),
            from: "",
            to: row.status,
            note: row.notes || "Application created",
          },
        ];
      }
      setTimelineById(nextTimeline);
    };
    load();
  }, [fetchApplications, fetchResumes, matchJobs]);

  useEffect(() => {
    if (!selected?.id) return undefined;
    const timer = window.setTimeout(async () => {
      await updateApplication(selected.id, { notes: selected.notes || "" });
    }, 700);
    return () => window.clearTimeout(timer);
  }, [selected?.notes]);

  const jobsById = useMemo(() => {
    const map = {};
    for (const job of jobs) map[job.id] = job;
    return map;
  }, [jobs]);

  const resumesById = useMemo(() => {
    const map = {};
    for (const resume of resumes) map[resume.id] = resume;
    return map;
  }, [resumes]);

  const filteredApps = useMemo(
    () => applications.filter((row) => withinDateRange(row, fromDate, toDate)),
    [applications, fromDate, toDate],
  );

  const grouped = useMemo(() => {
    const result = {
      saved: [],
      applied: [],
      interview: [],
      offer: [],
      rejected: [],
    };

    for (const row of filteredApps) {
      const status = COLUMN_ORDER.includes(row.status) ? row.status : "saved";
      result[status].push(row);
    }
    return result;
  }, [filteredApps]);

  const handleDragEnd = async (result) => {
    if (!result.destination) return;

    const sourceStatus = result.source.droppableId;
    const destinationStatus = result.destination.droppableId;
    if (sourceStatus === destinationStatus && result.source.index === result.destination.index) return;

    const moved = grouped[sourceStatus]?.[result.source.index];
    if (!moved) return;

    const updated = await updateApplication(moved.id, { status: destinationStatus });
    setApplications((prev) => prev.map((item) => (item.id === moved.id ? updated : item)));

    setTimelineById((prev) => ({
      ...prev,
      [moved.id]: [
        ...(prev[moved.id] || []),
        {
          id: `${moved.id}-${Date.now()}`,
          at: new Date().toISOString(),
          from: sourceStatus,
          to: destinationStatus,
          note: "Status updated from board",
        },
      ],
    }));

    if (selected?.id === moved.id) {
      setSelected((prev) => ({ ...prev, status: destinationStatus }));
    }
  };

  const totalCount = filteredApps.length;

  return (
    <>
      <div className="space-y-6">
        <section className="surface-card">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm text-gray-500">Total applications</p>
              <p className="text-2xl font-bold text-gray-900">{totalCount}</p>
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <label className="text-sm text-gray-600">
                From
                <input
                  type="date"
                  className="input-base mt-1"
                  value={fromDate}
                  onChange={(event) => setFromDate(event.target.value)}
                />
              </label>
              <label className="text-sm text-gray-600">
                To
                <input
                  type="date"
                  className="input-base mt-1"
                  value={toDate}
                  onChange={(event) => setToDate(event.target.value)}
                />
              </label>
            </div>
          </div>
        </section>

        {loading ? (
          <div className="surface-card">Loading applications...</div>
        ) : (
          <DragDropContext onDragEnd={handleDragEnd}>
            <div className="grid gap-4 xl:grid-cols-5">
              {COLUMN_ORDER.map((status) => (
                <StrictModeDroppable key={status} droppableId={status}>
                  {(provided, snapshot) => (
                    <section
                      ref={provided.innerRef}
                      {...provided.droppableProps}
                      className={`rounded-xl border p-3 ${snapshot.isDraggingOver ? "border-teal-300 bg-teal-50/50" : "border-gray-200 bg-white"}`}
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-gray-900">{COLUMN_MAP[status]}</h3>
                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600">
                          {grouped[status].length}
                        </span>
                      </div>

                      <div className="space-y-3">
                        {grouped[status].map((app, index) => {
                          const job = jobsById[app.job_id];
                          const resume = resumesById[app.resume_id];
                          return (
                            <Draggable key={String(app.id)} draggableId={String(app.id)} index={index}>
                              {(dragProvided) => (
                                <article
                                  ref={dragProvided.innerRef}
                                  {...dragProvided.draggableProps}
                                  {...dragProvided.dragHandleProps}
                                  style={dragProvided.draggableProps.style}
                                  onClick={() => setSelected(app)}
                                  className={`cursor-pointer rounded-lg border border-gray-200 border-l-4 bg-white p-3 shadow-sm ${BORDER_TONE[status]}`}
                                >
                                  <p className="text-sm font-semibold text-gray-900">{job?.title || `Job #${app.job_id}`}</p>
                                  <p className="text-xs text-gray-600">{job?.company || "Company"}</p>
                                  <p className="mt-1 text-xs text-gray-500">
                                    Applied {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "-"}
                                  </p>
                                  <span className="mt-2 inline-block rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600">
                                    {resume?.file_name || `Resume #${app.resume_id || "-"}`}
                                  </span>
                                </article>
                              )}
                            </Draggable>
                          );
                        })}
                        {provided.placeholder}
                      </div>
                    </section>
                  )}
                </StrictModeDroppable>
              ))}
            </div>
          </DragDropContext>
        )}
      </div>

      {selected ? (
        <div className="fixed inset-0 z-[115] flex justify-end">
          <button type="button" className="absolute inset-0 bg-black/30" onClick={() => setSelected(null)} />

          <aside className="relative h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-md">
            <h3 className="text-lg font-bold text-gray-900">Application details</h3>
            <p className="mt-1 text-sm text-gray-600">{jobsById[selected.job_id]?.title || `Job #${selected.job_id}`}</p>

            <div className="mt-4 grid gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-gray-500">Resume Used</p>
                <p className="text-sm text-gray-700">{resumesById[selected.resume_id]?.file_name || `Resume #${selected.resume_id || "-"}`}</p>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-gray-500">Status</p>
                <select
                  className="input-base mt-1"
                  value={selected.status}
                  onChange={async (event) => {
                    const nextStatus = event.target.value;
                    const updated = await updateApplication(selected.id, { status: nextStatus });
                    setApplications((prev) => prev.map((item) => (item.id === selected.id ? updated : item)));
                    setSelected((prev) => ({ ...prev, status: nextStatus }));
                    setTimelineById((prev) => ({
                      ...prev,
                      [selected.id]: [
                        ...(prev[selected.id] || []),
                        {
                          id: `${selected.id}-${Date.now()}`,
                          at: new Date().toISOString(),
                          from: selected.status,
                          to: nextStatus,
                          note: "Status changed from drawer",
                        },
                      ],
                    }));
                  }}
                >
                  {COLUMN_ORDER.map((status) => (
                    <option key={status} value={status}>
                      {COLUMN_MAP[status]}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-gray-500">Notes</p>
                <textarea
                  rows={4}
                  className="input-base mt-1"
                  value={selected.notes || ""}
                  onChange={(event) => setSelected((prev) => ({ ...prev, notes: event.target.value }))}
                />
                <p className="mt-1 text-xs text-gray-500">Notes auto-save after you stop typing.</p>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-gray-500">Timeline</p>
                <ul className="mt-2 space-y-2">
                  {(timelineById[selected.id] || []).map((event) => (
                    <li key={event.id} className="rounded-lg border border-gray-200 p-2 text-xs text-gray-600">
                      <p className="font-semibold text-gray-800">
                        {event.from ? `${COLUMN_MAP[event.from]} -> ` : ""}
                        {COLUMN_MAP[event.to] || event.to}
                      </p>
                      <p>{new Date(event.at).toLocaleString()}</p>
                      <p>{event.note}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
