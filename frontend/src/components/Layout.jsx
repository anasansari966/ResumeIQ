import { useMemo, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Menu } from "lucide-react";
import Sidebar from "./Sidebar";
import useAuth from "../hooks/useAuth";

function pageTitleFromPath(pathname) {
  if (pathname.includes("/resume/onboarding")) return "Upload Resume";
  if (pathname.startsWith("/resume/new")) return "Resume Builder";
  if (pathname.startsWith("/resume/")) return "Resume Editor";
  if (pathname.startsWith("/jobs")) return "Job Search";
  if (pathname.startsWith("/applications")) return "Applications";
  if (pathname.startsWith("/subscription")) return "Subscription";
  if (pathname.startsWith("/profile")) return "Profile";
  return "Dashboard";
}

function pageHintFromPath(pathname) {
  if (pathname.includes("/resume/onboarding")) return "Import a PDF or Word file and pick an ATS template.";
  if (pathname.startsWith("/resume/new")) return "Compose a polished resume from scratch.";
  if (pathname.startsWith("/resume/")) return "Edit content, template, and export options.";
  if (pathname.startsWith("/jobs")) return "Discover roles matched to your profile.";
  if (pathname.startsWith("/applications")) return "Track every opportunity from save to offer.";
  if (pathname.startsWith("/subscription")) return "Manage your plan and usage.";
  if (pathname.startsWith("/profile")) return "Account details and preferences.";
  return "Your career command center.";
}

export default function Layout({ title, children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useAuth();
  const location = useLocation();
  const finalTitle = useMemo(() => title || pageTitleFromPath(location.pathname), [title, location.pathname]);
  const hint = useMemo(() => pageHintFromPath(location.pathname), [location.pathname]);

  return (
    <div className="app-canvas min-h-screen">
      <Sidebar mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} />

      <div className="lg:pl-[var(--sidebar-width)]">
        <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/80 backdrop-blur-md">
          <div className="flex h-[4.25rem] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                className="rounded-xl border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50 lg:hidden"
                onClick={() => setMobileOpen(true)}
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="min-w-0 animate-fade-in">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-teal-700">ResumeIQ</p>
                <h1 className="font-display truncate text-xl font-bold text-slate-900 sm:text-2xl">{finalTitle}</h1>
                <p className="hidden truncate text-xs text-slate-500 sm:block">{hint}</p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-semibold text-slate-800">{user?.name || "User"}</p>
                <p className="text-xs text-slate-500">{user?.email || ""}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-100 font-semibold text-teal-800">
                {(user?.name?.[0] || user?.email?.[0] || "U").toUpperCase()}
              </div>
            </div>
          </div>
        </header>

        <main className="animate-fade-up px-4 py-6 sm:px-6 lg:px-8">{children ?? <Outlet />}</main>
      </div>
    </div>
  );
}
