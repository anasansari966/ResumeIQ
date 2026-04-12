function inferVariant(template, templateId) {
  const variant = (template?.preview_variant || "").trim().toLowerCase();
  if (variant) return variant;
  const source = `${template?.name || ""} ${templateId || ""}`.toLowerCase();
  if (source.includes("folder_") || source.includes("template1") || source.includes("classic")) {
    return "sidebar-classic";
  }
  if (source.includes("research") || source.includes("robot")) return "research";
  if (source.includes("minimal") || source.includes("puneet")) return "minimal";
  return "clean";
}

function textListFromValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(/\r?\n+/)
      .map((item) => item.replace(/^[-*]\s*/, "").trim())
      .filter(Boolean);
  }
  return [];
}

function tagListFromValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(/,|\r?\n+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function experienceHighlights(item) {
  return [
    ...textListFromValue(item?.bullets),
    ...textListFromValue(item?.highlights),
    ...textListFromValue(item?.description),
  ].slice(0, 2);
}

function previewDataFromResume(resume) {
  const parsed = resume?.parsed_json || resume || {};
  const contact = parsed.contact || {};
  const experience = Array.isArray(parsed.experience) ? parsed.experience.filter(Boolean) : [];
  const education = Array.isArray(parsed.education) ? parsed.education.filter(Boolean) : [];
  const skills =
    Array.isArray(parsed.skills) || typeof parsed.skills === "string"
      ? { technical: parsed.skills }
      : parsed.skills || {};
  const technical = tagListFromValue(skills.technical);
  const tools = tagListFromValue(skills.tools);
  const soft = tagListFromValue(skills.soft || skills.other);
  const mergedSkills = [...new Set([...technical, ...tools, ...soft])].slice(0, 10);

  const name = String(contact.name || parsed.name || "").trim() || "Candidate Name";
  const headline =
    String(parsed.title || experience[0]?.title || "").trim() ||
    (mergedSkills[0] ? `${mergedSkills[0]} Specialist` : "Professional Resume");
  const summary =
    String(parsed.summary || parsed.profile || "").trim() ||
    "A concise personal summary appears here, showcasing value, strengths, and the overall tone of the selected template.";

  return {
    name,
    headline,
    email: String(contact.email || "").trim() || "candidate@example.com",
    phone: String(contact.phone || "").trim() || "+1 555 010 2026",
    location: String(contact.location || contact.city || "").trim() || "Open to remote and hybrid roles",
    linkedin: String(contact.linkedin || "").trim(),
    summary,
    experience: experience.slice(0, 3),
    education: education.slice(0, 2),
    skills: mergedSkills.length ? mergedSkills : ["Python", "FastAPI", "React", "SQL", "Leadership", "Analysis"],
  };
}

function themeForVariant(variant) {
  if (variant === "sidebar-classic") {
    return {
      accent: "#2563eb",
      accentSoft: "rgba(37,99,235,0.14)",
      shell: "linear-gradient(180deg, rgba(239,246,255,0.92) 0%, rgba(219,234,254,0.76) 100%)",
      paper: "#ffffff",
      ink: "#0f172a",
      muted: "#475569",
      rail: "linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%)",
      badge: "#dbeafe",
      badgeText: "#1d4ed8",
    };
  }
  if (variant === "research") {
    return {
      accent: "#0ea5e9",
      accentSoft: "rgba(14,165,233,0.16)",
      shell: "linear-gradient(180deg, rgba(8,47,73,0.35) 0%, rgba(15,23,42,0.72) 100%)",
      paper: "#f8fafc",
      ink: "#0f172a",
      muted: "#526074",
      rail: "linear-gradient(135deg, #0f172a 0%, #082f49 100%)",
      badge: "#e0f2fe",
      badgeText: "#0369a1",
    };
  }
  if (variant === "minimal") {
    return {
      accent: "#7c3aed",
      accentSoft: "rgba(124,58,237,0.16)",
      shell: "linear-gradient(180deg, rgba(243,232,255,0.9) 0%, rgba(255,255,255,0.82) 100%)",
      paper: "#ffffff",
      ink: "#1f1635",
      muted: "#5b5370",
      rail: "linear-gradient(180deg, #faf5ff 0%, #ede9fe 100%)",
      badge: "#f3e8ff",
      badgeText: "#6d28d9",
    };
  }
  return {
    accent: "#0f766e",
    accentSoft: "rgba(15,118,110,0.14)",
    shell: "linear-gradient(180deg, rgba(236,253,250,0.9) 0%, rgba(255,255,255,0.82) 100%)",
    paper: "#ffffff",
    ink: "#102a2a",
    muted: "#4b6363",
    rail: "linear-gradient(180deg, #f0fdfa 0%, #ccfbf1 100%)",
    badge: "#ccfbf1",
    badgeText: "#0f766e",
  };
}

function SectionCard({ title, children, delay = 0 }) {
  return (
    <section className="resume-preview-reveal rounded-3xl border border-black/5 bg-white/80 p-4 shadow-[0_14px_32px_rgba(15,23,42,0.05)]" style={{ animationDelay: `${delay}ms` }}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--preview-accent)]">{title}</p>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function ModernPreview({ data, template, variant }) {
  const theme = themeForVariant(variant);

  return (
    <div
      className="resume-preview-shell resume-preview-reveal group h-full overflow-hidden rounded-[28px] border border-white/10 p-3 sm:p-4"
      style={{
        "--preview-accent": theme.accent,
        "--preview-accent-soft": theme.accentSoft,
        "--preview-ink": theme.ink,
        "--preview-muted": theme.muted,
        background: theme.shell,
      }}
    >
      <div className="resume-preview-paper animate-float-soft relative overflow-hidden rounded-[24px] border border-black/5 shadow-[0_30px_80px_rgba(15,23,42,0.16)]" style={{ background: theme.paper }}>
        <div className="resume-preview-sheen" />
        <header className="relative overflow-hidden px-5 py-5 sm:px-7 sm:py-6" style={{ background: theme.rail }}>
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.55),transparent_35%)]" />
          <div className="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[var(--preview-accent)]/90">
                {template?.name || "Resume Template"}
              </p>
              <h3 className="mt-2 text-[1.6rem] font-bold leading-tight text-[var(--preview-ink)] sm:text-[1.9rem]">
                {data.name}
              </h3>
              <p className="mt-1 text-sm font-semibold text-[var(--preview-accent)]">{data.headline}</p>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[color:var(--preview-muted)]">{data.summary}</p>
            </div>
            <div className="flex max-w-xs flex-wrap gap-2 lg:justify-end">
              {[data.email, data.phone, data.location].filter(Boolean).map((item) => (
                <span
                  key={item}
                  className="rounded-full border border-black/5 bg-white/70 px-3 py-1.5 text-[11px] font-medium text-[var(--preview-ink)] shadow-sm backdrop-blur"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        </header>

        <div className="grid gap-4 px-4 py-4 sm:px-5 sm:py-5 lg:grid-cols-[1.25fr,0.85fr]">
          <SectionCard title="Experience" delay={80}>
            <div className="space-y-4">
              {data.experience.length ? (
                data.experience.map((item, idx) => (
                  <article key={`${item.company || "exp"}-${idx}`} className="flex gap-3">
                    <div className="mt-1 h-3 w-3 shrink-0 rounded-full border-[5px] border-[var(--preview-accent-soft)] bg-[var(--preview-accent)]" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--preview-ink)]">{item.title || "Experience role"}</p>
                      <p className="mt-0.5 text-[12px] text-[color:var(--preview-muted)]">
                        {[item.company, item.start_date, item.end_date].filter(Boolean).join(" • ") || "Company • Recent"}
                      </p>
                      {(item.bullets || item.description || []).slice(0, 2).map((bullet, bulletIdx) => (
                        <p key={`${idx}-${bulletIdx}`} className="mt-2 text-[12px] leading-5 text-[color:var(--preview-muted)]">
                          • {bullet}
                        </p>
                      ))}
                    </div>
                  </article>
                ))
              ) : (
                <p className="text-sm text-[color:var(--preview-muted)]">Add experience to populate this preview.</p>
              )}
            </div>
          </SectionCard>

          <div className="space-y-4">
            <SectionCard title="Skills" delay={160}>
              <div className="flex flex-wrap gap-2">
                {data.skills.map((skill, idx) => (
                  <span
                    key={`${skill}-${idx}`}
                    className="resume-preview-chip rounded-full px-3 py-1.5 text-[11px] font-semibold"
                    style={{ background: theme.badge, color: theme.badgeText }}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Education" delay={240}>
              <div className="space-y-3">
                {data.education.length ? (
                  data.education.map((item, idx) => (
                    <article key={`${item.institution || "edu"}-${idx}`} className="rounded-2xl border border-black/5 bg-black/[0.015] px-3 py-3">
                      <p className="text-sm font-semibold text-[var(--preview-ink)]">{item.degree || "Degree"}</p>
                      <p className="mt-0.5 text-[12px] text-[color:var(--preview-muted)]">
                        {[item.institution, item.year].filter(Boolean).join(" • ") || "Institution • Year"}
                      </p>
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-[color:var(--preview-muted)]">Add education to populate this preview.</p>
                )}
              </div>
            </SectionCard>
          </div>
        </div>
      </div>
    </div>
  );
}

function SidebarPreview({ data, template }) {
  const theme = themeForVariant("sidebar-classic");
  return (
    <div
      className="resume-preview-shell resume-preview-reveal h-full overflow-hidden rounded-[28px] border border-white/10 p-3 sm:p-4"
      style={{
        "--preview-accent": theme.accent,
        "--preview-accent-soft": theme.accentSoft,
        "--preview-ink": theme.ink,
        "--preview-muted": theme.muted,
        background: theme.shell,
      }}
    >
      <div className="resume-preview-paper animate-float-soft grid min-h-full overflow-hidden rounded-[24px] border border-black/5 shadow-[0_30px_80px_rgba(15,23,42,0.18)] lg:grid-cols-[220px,1fr]" style={{ background: theme.paper }}>
        <div className="resume-preview-sheen" />
        <aside className="relative border-b border-black/5 px-5 py-6 lg:border-b-0 lg:border-r lg:px-5" style={{ background: theme.rail }}>
          <div className="absolute inset-y-0 right-0 hidden w-px border-r border-dashed border-[var(--preview-accent)]/40 lg:block" />
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[var(--preview-accent)]/90">
            {template?.name || "Template"}
          </p>
          <h3 className="mt-4 text-xl font-bold leading-tight text-[var(--preview-ink)]">{data.name}</h3>
          <p className="mt-2 text-sm font-semibold text-[var(--preview-accent)]">{data.headline}</p>
          <div className="mt-5 space-y-2 text-[12px] leading-5 text-[color:var(--preview-muted)]">
            <p>{data.email}</p>
            <p>{data.phone}</p>
            <p>{data.location}</p>
            {data.linkedin && <p>{data.linkedin}</p>}
          </div>
          <div className="mt-6 space-y-2">
            {data.skills.slice(0, 6).map((skill, idx) => (
              <div
                key={`${skill}-${idx}`}
                className="resume-preview-chip rounded-full px-3 py-1.5 text-[11px] font-semibold"
                style={{ background: theme.badge, color: theme.badgeText }}
              >
                {skill}
              </div>
            ))}
          </div>
        </aside>

        <div className="px-5 py-5 sm:px-6">
          <div className="resume-preview-reveal" style={{ animationDelay: "80ms" }}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--preview-accent)]">Profile</p>
            <p className="mt-2 text-sm leading-6 text-[color:var(--preview-muted)]">{data.summary}</p>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[0.9fr,1.1fr]">
            <SectionCard title="Education" delay={160}>
              <div className="space-y-3">
                {data.education.length ? (
                  data.education.map((item, idx) => (
                    <article key={`${item.institution || "edu"}-${idx}`}>
                      <p className="text-[12px] font-semibold text-[var(--preview-accent)]">{item.year || "Year"}</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--preview-ink)]">{item.degree || "Degree"}</p>
                      <p className="mt-0.5 text-[12px] text-[color:var(--preview-muted)]">{item.institution || "Institution"}</p>
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-[color:var(--preview-muted)]">Add education to populate this preview.</p>
                )}
              </div>
            </SectionCard>

            <SectionCard title="Experience" delay={240}>
              <div className="space-y-4">
                {data.experience.length ? (
                  data.experience.map((item, idx) => (
                    <article key={`${item.company || "exp"}-${idx}`}>
                      <p className="text-[12px] font-semibold text-[var(--preview-accent)]">
                        {[item.start_date, item.end_date].filter(Boolean).join(" - ") || "Recent"}
                      </p>
                      <p className="mt-1 text-sm font-semibold text-[var(--preview-ink)]">{item.title || "Role"}</p>
                      <p className="mt-0.5 text-[12px] text-[color:var(--preview-muted)]">{item.company || "Company"}</p>
                      {(item.bullets || item.description || []).slice(0, 2).map((bullet, bulletIdx) => (
                        <p key={`${idx}-${bulletIdx}`} className="mt-2 text-[12px] leading-5 text-[color:var(--preview-muted)]">
                          • {bullet}
                        </p>
                      ))}
                    </article>
                  ))
                ) : (
                  <p className="text-sm text-[color:var(--preview-muted)]">Add experience to populate this preview.</p>
                )}
              </div>
            </SectionCard>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DocxTemplatePreview({ template, templateId, resume, className = "" }) {
  const variant = inferVariant(template, templateId);
  const data = previewDataFromResume(resume);

  return (
    <div className={`w-full min-h-[280px] ${className}`}>
      {variant === "sidebar-classic" ? (
        <SidebarPreview data={data} template={template} />
      ) : (
        <ModernPreview data={data} template={template} variant={variant} />
      )}
    </div>
  );
}
