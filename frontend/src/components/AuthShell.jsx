import { Link } from "react-router-dom";
import { VISUALS } from "../theme/visuals";

export default function AuthShell({
  children,
  headline = "Build smarter resumes and land better interviews.",
  subcopy = "AI-assisted editing, ATS templates, and job tracking in one career workspace.",
}) {
  return (
    <div className="auth-atmosphere relative min-h-screen overflow-hidden lg:grid lg:grid-cols-2">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage: `url(${VISUALS.loginHero})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
          mixBlendMode: "luminosity",
        }}
      />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[#0b1324]/80 via-[#0b1324]/55 to-teal-950/40" />

      <aside className="relative z-10 hidden flex-col justify-between p-10 text-white lg:flex xl:p-14">
        <Link to="/login" className="font-display text-3xl font-extrabold tracking-tight text-white">
          Resume<span className="text-teal-300">IQ</span>
        </Link>

        <div className="max-w-lg animate-fade-up space-y-5">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-teal-200/90">Career workspace</p>
          <h1 className="font-display text-4xl font-bold leading-[1.15] xl:text-5xl">{headline}</h1>
          <p className="max-w-md text-base leading-relaxed text-slate-300">{subcopy}</p>
          <ul className="mt-6 space-y-2 text-sm text-slate-300">
            <li className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
              ATS-ready LaTeX templates
            </li>
            <li className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
              Live preview before you export
            </li>
            <li className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
              Jobs and applications in one place
            </li>
          </ul>
        </div>

        <p className="text-xs text-slate-500">ResumeIQ · Professional resume intelligence</p>
      </aside>

      <main className="relative z-10 flex items-center justify-center px-4 py-10 sm:px-6 lg:bg-slate-50/95 lg:backdrop-blur-sm">
        <div className="absolute left-4 top-4 z-20 lg:hidden">
          <Link to="/login" className="font-display text-2xl font-extrabold tracking-tight text-white">
            Resume<span className="text-teal-300">IQ</span>
          </Link>
        </div>
        <div className="w-full max-w-md animate-fade-up">{children}</div>
      </main>
    </div>
  );
}
