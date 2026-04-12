const base = () => (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

function headers(extra = {}) {
  const h = { ...extra };
  const token = localStorage.getItem("resumeiq_token");
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function api(path, options = {}) {
  const url = `${base()}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: headers(options.headers),
  });
  if (res.status === 401) {
    localStorage.removeItem("resumeiq_token");
    window.dispatchEvent(new Event("resumeiq:logout"));
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const msg = data?.detail || data || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export function setToken(t) {
  if (t) localStorage.setItem("resumeiq_token", t);
  else localStorage.removeItem("resumeiq_token");
}

export function getToken() {
  return localStorage.getItem("resumeiq_token");
}
