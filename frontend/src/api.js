import axios from "axios";

/**
 * All data and auth live on the FastAPI app. The UI only calls this prefix
 * (same-origin in production and Vite dev via /api proxy).
 */
const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
export const API_PREFIX = "/api/v1";
const axiosBaseURL = API_ORIGIN ? `${API_ORIGIN}${API_PREFIX}` : API_PREFIX;

/** Build absolute URL for public template preview images (same rules as axios base). */
export function templatePreviewSrc(previewUrl) {
  if (!previewUrl) return "";
  const path = previewUrl.startsWith("/") ? previewUrl : `/${previewUrl}`;
  return API_ORIGIN ? `${API_ORIGIN}${path}` : path;
}

const LOGIN_PATH = "/login";
const LOGIN_SKIP_PATHS = ["/auth/login"];
const REFRESH_SKIP_PATHS = ["/auth/refresh"];
const FRONTEND_BASE = (import.meta.env.VITE_FRONTEND_URL || import.meta.env.VITE_APP_URL || "").replace(/\/$/, "");

export const getAccessToken = () => localStorage.getItem("access_token");
export const getRefreshToken = () => localStorage.getItem("refresh_token");

export const setTokens = (accessToken, refreshToken = "") => {
  if (accessToken) {
    localStorage.setItem("access_token", accessToken);
  }
  if (refreshToken) {
    localStorage.setItem("refresh_token", refreshToken);
  }
};

export const clearTokens = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  try {
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem("resume_onboarding_done");
    }
  } catch {
    /* ignore */
  }
};

const api = axios.create({
  baseURL: axiosBaseURL,
  timeout: 30000,
});

api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

let refreshPromise = null;

function buildLoginUrl() {
  if (typeof window === "undefined") return LOGIN_PATH;

  const next = encodeURIComponent(`${window.location.pathname}${window.location.search}${window.location.hash}`);

  if (FRONTEND_BASE) {
    return `${FRONTEND_BASE}${LOGIN_PATH}?next=${next}`;
  }

  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const isLikelyApiPort = ["8000", "8001"].includes(window.location.port);
  if (isLocalHost && isLikelyApiPort) {
    return `${window.location.protocol}//${window.location.hostname}:5173${LOGIN_PATH}?next=${next}`;
  }

  return `${LOGIN_PATH}?next=${next}`;
}

const redirectToLogin = () => {
  clearTokens();
  if (typeof window !== "undefined") {
    const target = buildLoginUrl();
    const targetUrl = new URL(target, window.location.origin);
    const alreadyOnSameLogin =
      targetUrl.origin === window.location.origin && window.location.pathname.startsWith(LOGIN_PATH);
    if (!alreadyOnSameLogin) {
      window.location.assign(targetUrl.toString());
    }
  }
};

const refreshAccessToken = async () => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error("Missing refresh token");
  }

  const refreshUrl = `${axiosBaseURL}/auth/refresh`;
  const response = await axios.post(refreshUrl, {
    refresh_token: refreshToken,
  });

  const nextAccess = response.data?.access_token;
  const nextRefresh = response.data?.refresh_token || refreshToken;

  if (!nextAccess) {
    throw new Error("Invalid refresh response");
  }

  setTokens(nextAccess, nextRefresh);
  return nextAccess;
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;
    const url = String(originalRequest?.url || "");

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !LOGIN_SKIP_PATHS.some((path) => url.includes(path)) &&
      !REFRESH_SKIP_PATHS.some((path) => url.includes(path))
    ) {
      originalRequest._retry = true;

      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null;
          });
        }

        const token = await refreshPromise;
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return api(originalRequest);
      } catch (refreshError) {
        redirectToLogin();
        return Promise.reject(refreshError);
      }
    }

    if (status === 401) {
      redirectToLogin();
    }

    return Promise.reject(error);
  },
);

export const getToken = getAccessToken;
export const setToken = (token) => {
  if (token) {
    localStorage.setItem("access_token", token);
  } else {
    localStorage.removeItem("access_token");
  }
};

export default api;
