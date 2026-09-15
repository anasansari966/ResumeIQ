import { NavLink, useLocation } from "react-router-dom";
import {
  Briefcase,
  Crown,
  FilePlus2,
  KanbanSquare,
  LayoutDashboard,
  LogOut,
  UploadCloud,
  User,
  X,
} from "lucide-react";
import useAuth from "../hooks/useAuth";

const navItems = [
  { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { label: "Upload Resume", path: "/resume/onboarding", icon: UploadCloud },
  { label: "Resume Builder", path: "/resume/new", icon: FilePlus2 },
  { label: "Job Search", path: "/jobs", icon: Briefcase },
  { label: "Applications", path: "/applications", icon: KanbanSquare },
  { label: "Subscription", path: "/subscription", icon: Crown },
  { label: "Profile", path: "/profile", icon: User },
];

export default function Sidebar({ mobileOpen, setMobileOpen }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  const isItemActive = (item, isActive) => {
    if (item.path === "/resume/new") {
      return location.pathname.startsWith("/resume/") && !location.pathname.includes("onboarding");
    }
    if (item.path === "/resume/onboarding") {
      return location.pathname.includes("onboarding");
    }
    return isActive;
  };

  return (
    <>
      {mobileOpen ? (
        <button
          type="button"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-[#0b1324]/50 backdrop-blur-[2px] lg:hidden"
          aria-label="Close sidebar"
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[var(--sidebar-width)] flex-col border-r border-white/5 bg-[var(--color-ink)] px-4 py-5 text-white shadow-[4px_0_24px_rgba(11,19,36,0.18)] transition-transform duration-300 lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-8 flex items-start justify-between gap-3 px-2">
          <div className="animate-slide-in">
            <p className="font-display text-2xl font-extrabold tracking-tight">
              Resume<span className="text-teal-300">IQ</span>
            </p>
            <p className="mt-1 text-xs text-slate-400">Career workspace</p>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white lg:hidden"
            onClick={() => setMobileOpen(false)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto">
          {navItems.map((item, index) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileOpen(false)}
                style={{ animationDelay: `${index * 40}ms` }}
                className={({ isActive }) =>
                  `nav-link animate-slide-in ${
                    isItemActive(item, isActive) ? "nav-link-active" : "nav-link-idle"
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0 opacity-90" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
          <div className="mb-3 flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-500/20 font-semibold text-teal-200">
              {(user?.name?.[0] || user?.email?.[0] || "U").toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-white">{user?.name || "User"}</p>
              <p className="truncate text-xs text-slate-400">{user?.email || ""}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-[#152238] px-3 py-2.5 text-sm font-semibold text-slate-200 hover:border-red-400/30 hover:bg-red-500/10 hover:text-red-200"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </aside>
    </>
  );
}
