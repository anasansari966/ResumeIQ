import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

/** App is served under /resumeiq/ when bundled behind FastAPI (same origin as /api). */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Default matches local ResumeIQ API. Override with VITE_DEV_API_TARGET.
  // Prefer 8765 — 8010 can be occupied by stale Windows listeners.
  const proxyTarget = env.VITE_DEV_API_TARGET || "http://127.0.0.1:8765";
  const base = env.VITE_BASE || "/resumeiq/";
  const basePath = base.replace(/\/$/, "");

  /** Dev visits to /resumeiq (no trailing slash) must redirect or Vite shows only a base-URL warning. */
  function redirectBaseWithoutTrailingSlash() {
    if (!basePath) return null;
    return {
      name: "redirect-base-without-trailing-slash",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const raw = req.url || "";
          const pathOnly = raw.split("?")[0] ?? "";
          if (pathOnly === basePath) {
            const qs = raw.includes("?") ? raw.slice(raw.indexOf("?")) : "";
            res.writeHead(302, { Location: `${basePath}/${qs}` });
            res.end();
            return;
          }
          next();
        });
      },
    };
  }

  return {
    base,
    plugins: [react(), redirectBaseWithoutTrailingSlash()].filter(Boolean),
    server: {
      port: 5173,
      proxy: {
        "/api": { target: proxyTarget, changeOrigin: true },
        "/health": { target: proxyTarget, changeOrigin: true },
      },
    },
  };
});
