/** First-time resume upload + template selection — persisted per user across sessions. */

export function resumeOnboardingStorageKey(userId) {
  if (userId == null || userId === "") return null;
  return `resumeiq_onboarding_done_${userId}`;
}

export function isResumeOnboardingDone(userId) {
  if (typeof window === "undefined" || userId == null || userId === "") return false;
  const key = resumeOnboardingStorageKey(userId);
  if (!key) return false;
  return window.localStorage.getItem(key) === "true";
}

export function setResumeOnboardingDone(userId) {
  if (typeof window === "undefined" || userId == null || userId === "") return;
  const key = resumeOnboardingStorageKey(userId);
  if (!key) return;
  window.localStorage.setItem(key, "true");
  try {
    window.sessionStorage.removeItem("resume_onboarding_done");
  } catch {
    /* ignore */
  }
}

/** One-time: old builds used sessionStorage; copy to per-user localStorage. */
export function migrateSessionOnboardingToUser(userId) {
  if (typeof window === "undefined" || userId == null || userId === "") return;
  try {
    if (window.sessionStorage.getItem("resume_onboarding_done") === "true") {
      setResumeOnboardingDone(userId);
    }
  } catch {
    /* ignore */
  }
}
