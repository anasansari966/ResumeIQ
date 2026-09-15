import { useMemo, useState } from "react";
import ConfirmModal from "../components/ConfirmModal";
import useAuth from "../hooks/useAuth";
import { useToast } from "../components/Toast";

function strength(password) {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score += 1;
  if (score <= 1) return { label: "Weak", tone: "text-red-600", bar: "w-1/3 bg-red-500" };
  if (score === 2) return { label: "Medium", tone: "text-amber-600", bar: "w-2/3 bg-amber-500" };
  return { label: "Strong", tone: "text-emerald-600", bar: "w-full bg-emerald-500" };
}

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const [tab, setTab] = useState("personal");

  const [profile, setProfile] = useState({
    fullName: user?.name || "",
    email: user?.email || "",
    phone: "",
    location: "",
    linkedin: "",
    portfolio: "",
    avatarName: "",
  });

  const [security, setSecurity] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });

  const [prefs, setPrefs] = useState(() => ({
    jobRecommendations: true,
    reminders: true,
    weeklyDigest: false,
    defaultTemplate: localStorage.getItem("pref_template") || "latex_ats_clean",
    defaultExport: localStorage.getItem("pref_export") || "pdf",
  }));

  const [deleteOpen, setDeleteOpen] = useState(false);

  const passwordStrength = useMemo(() => strength(security.newPassword), [security.newPassword]);

  const saveProfile = () => {
    showToast({ type: "success", message: "Profile saved locally." });
  };

  const savePassword = () => {
    if (security.newPassword.length < 8) {
      showToast({ type: "warning", message: "Password must be at least 8 characters." });
      return;
    }
    if (security.newPassword !== security.confirmPassword) {
      showToast({ type: "warning", message: "Passwords do not match." });
      return;
    }
    showToast({ type: "success", message: "Password updated." });
    setSecurity({ currentPassword: "", newPassword: "", confirmPassword: "" });
  };

  const savePreferences = () => {
    localStorage.setItem("pref_template", prefs.defaultTemplate);
    localStorage.setItem("pref_export", prefs.defaultExport);
    showToast({ type: "success", message: "Preferences saved." });
  };

  return (
    <>
      <div className="space-y-6">
        <section className="surface-card">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === "personal" ? "bg-teal-500 text-white" : "bg-gray-100 text-gray-600"}`}
              onClick={() => setTab("personal")}
            >
              Personal Info
            </button>
            <button
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === "security" ? "bg-teal-500 text-white" : "bg-gray-100 text-gray-600"}`}
              onClick={() => setTab("security")}
            >
              Security
            </button>
            <button
              type="button"
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${tab === "preferences" ? "bg-teal-500 text-white" : "bg-gray-100 text-gray-600"}`}
              onClick={() => setTab("preferences")}
            >
              Preferences
            </button>
          </div>
        </section>

        {tab === "personal" ? (
          <section className="surface-card space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-teal-100 text-xl font-bold text-teal-700">
                {(profile.fullName?.[0] || profile.email?.[0] || "U").toUpperCase()}
              </div>
              <div>
                <label className="btn-secondary cursor-pointer">
                  Upload Avatar
                  <input
                    type="file"
                    className="hidden"
                    onChange={(event) =>
                      setProfile((prev) => ({
                        ...prev,
                        avatarName: event.target.files?.[0]?.name || "",
                      }))
                    }
                  />
                </label>
                {profile.avatarName ? <p className="mt-1 text-xs text-gray-500">{profile.avatarName}</p> : null}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Full Name</label>
                <input
                  className="input-base"
                  value={profile.fullName}
                  onChange={(event) => setProfile((prev) => ({ ...prev, fullName: event.target.value }))}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Email</label>
                <input className="input-base bg-gray-50" value={profile.email} disabled />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Phone</label>
                <input
                  className="input-base"
                  value={profile.phone}
                  onChange={(event) => setProfile((prev) => ({ ...prev, phone: event.target.value }))}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Location</label>
                <input
                  className="input-base"
                  value={profile.location}
                  onChange={(event) => setProfile((prev) => ({ ...prev, location: event.target.value }))}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">LinkedIn URL</label>
                <input
                  className="input-base"
                  value={profile.linkedin}
                  onChange={(event) => setProfile((prev) => ({ ...prev, linkedin: event.target.value }))}
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Portfolio URL</label>
                <input
                  className="input-base"
                  value={profile.portfolio}
                  onChange={(event) => setProfile((prev) => ({ ...prev, portfolio: event.target.value }))}
                />
              </div>
            </div>

            <button type="button" className="btn-primary" onClick={saveProfile}>
              Save Changes
            </button>
          </section>
        ) : null}

        {tab === "security" ? (
          <section className="surface-card space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Security</h2>
            <div className="grid gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Current Password</label>
                <input
                  type="password"
                  className="input-base"
                  value={security.currentPassword}
                  onChange={(event) => setSecurity((prev) => ({ ...prev, currentPassword: event.target.value }))}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">New Password</label>
                <input
                  type="password"
                  className="input-base"
                  value={security.newPassword}
                  onChange={(event) => setSecurity((prev) => ({ ...prev, newPassword: event.target.value }))}
                />
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-200">
                  <div className={`h-full ${passwordStrength.bar}`} />
                </div>
                <p className={`mt-1 text-xs ${passwordStrength.tone}`}>{passwordStrength.label}</p>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Confirm Password</label>
                <input
                  type="password"
                  className="input-base"
                  value={security.confirmPassword}
                  onChange={(event) => setSecurity((prev) => ({ ...prev, confirmPassword: event.target.value }))}
                />
              </div>
            </div>

            <button type="button" className="btn-primary" onClick={savePassword}>
              Save Password
            </button>

            <div className="rounded-xl border border-red-200 bg-red-50 p-4">
              <p className="text-sm font-semibold text-red-700">Danger Zone</p>
              <p className="mt-1 text-sm text-red-600">Delete your account permanently from this workspace.</p>
              <button type="button" className="btn-danger mt-3" onClick={() => setDeleteOpen(true)}>
                Delete Account
              </button>
            </div>
          </section>
        ) : null}

        {tab === "preferences" ? (
          <section className="surface-card space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Preferences</h2>

            <div className="space-y-2 text-sm text-gray-700">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={prefs.jobRecommendations}
                  onChange={(event) => setPrefs((prev) => ({ ...prev, jobRecommendations: event.target.checked }))}
                />
                Job recommendations
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={prefs.reminders}
                  onChange={(event) => setPrefs((prev) => ({ ...prev, reminders: event.target.checked }))}
                />
                Application reminders
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={prefs.weeklyDigest}
                  onChange={(event) => setPrefs((prev) => ({ ...prev, weeklyDigest: event.target.checked }))}
                />
                Weekly digest
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Default template</label>
                <select
                  className="input-base"
                  value={prefs.defaultTemplate}
                  onChange={(event) => setPrefs((prev) => ({ ...prev, defaultTemplate: event.target.value }))}
                >
                  <option value="latex_ats_clean">ATS Clean</option>
                  <option value="latex_executive_navy">Executive Navy</option>
                  <option value="latex_modern_emerald">Modern Emerald</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Default export format</label>
                <select
                  className="input-base"
                  value={prefs.defaultExport}
                  onChange={(event) => setPrefs((prev) => ({ ...prev, defaultExport: event.target.value }))}
                >
                  <option value="pdf">PDF</option>
                  <option value="docx">DOCX</option>
                </select>
              </div>
            </div>

            <button type="button" className="btn-primary" onClick={savePreferences}>
              Save Preferences
            </button>
          </section>
        ) : null}
      </div>

      <ConfirmModal
        isOpen={deleteOpen}
        title="Delete Account"
        message="This will sign you out and remove local access immediately. Continue?"
        danger
        confirmText="Delete"
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => {
          setDeleteOpen(false);
          logout();
        }}
      />
    </>
  );
}
