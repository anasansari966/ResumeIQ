import { useCallback, useState } from "react";
import api from "../api";
import { useToast } from "../components/Toast";

const PDF_FALLBACK_WARN_KEY = "resumeiq_pdf_fallback_warned";

function buildTextFromResumeJson(resumeJson) {
  const contact = resumeJson?.contact || {};
  const lines = [
    String(contact.name || "Candidate"),
    String(contact.email || ""),
    String(contact.phone || ""),
    String(resumeJson?.summary || ""),
  ].filter(Boolean);
  return lines.join("\n");
}

function triggerFileDownload(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

async function detailMessageFromAxiosError(error, fallback) {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      try {
        const j = JSON.parse(text);
        const d = j.detail;
        if (typeof d === "string") return d;
        if (Array.isArray(d)) return d.map((x) => (typeof x === "string" ? x : x.msg || JSON.stringify(x))).join(" ");
      } catch {
        if (text) return text;
      }
    } catch {
      /* ignore */
    }
    return fallback;
  }
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (typeof x === "string" ? x : x.msg || "")).filter(Boolean).join(" ") || fallback;
  return fallback;
}

export default function useResumes() {
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(false);
  const { showToast } = useToast();

  const fetchResumes = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/resumes");
      setResumes(response.data || []);
      return response.data || [];
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Failed to fetch resumes." });
      return [];
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const createResume = useCallback(
    async (resumeJson) => {
      try {
        const response = await api.post("/resumes", { parsed_json: resumeJson });
        await fetchResumes();
        return response.data;
      } catch {
        try {
          const text = buildTextFromResumeJson(resumeJson);
          const fd = new FormData();
          const file = new File([text || "ResumeIQ draft"], "resume-draft.txt", { type: "text/plain" });
          fd.append("file", file);
          const upload = await api.post("/resumes/upload", fd, { timeout: 180000 });
          const resumeId = upload.data?.id;
          if (!resumeId) throw new Error("Draft upload failed");
          const updated = await api.patch(`/resumes/${resumeId}`, {
            parsed_json: resumeJson,
            recalc_ats: true,
          });
          await fetchResumes();
          return updated.data;
        } catch (error) {
          showToast({ type: "error", message: error.response?.data?.detail || "Could not create resume." });
          throw error;
        }
      }
    },
    [fetchResumes, showToast],
  );

  const updateResume = useCallback(
    async (id, resumeJson) => {
      try {
        const response = await api.put(`/resumes/${id}`, { parsed_json: resumeJson });
        await fetchResumes();
        return response.data;
      } catch {
        try {
          const response = await api.patch(`/resumes/${id}`, {
            parsed_json: resumeJson,
            recalc_ats: true,
          });
          await fetchResumes();
          return response.data;
        } catch (error) {
          showToast({ type: "error", message: error.response?.data?.detail || "Could not update resume." });
          throw error;
        }
      }
    },
    [fetchResumes, showToast],
  );

  const getResume = useCallback(
    async (id) => {
      try {
        const response = await api.get(`/resumes/${id}`);
        return response.data;
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Resume not found." });
        throw error;
      }
    },
    [showToast],
  );

  const deleteResume = useCallback(
    async (id) => {
      try {
        await api.delete(`/resumes/${id}`);
        await fetchResumes();
        showToast({ type: "success", message: "Resume deleted." });
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Could not delete resume." });
        throw error;
      }
    },
    [fetchResumes, showToast],
  );

  const duplicateResume = useCallback(
    async (resume) => {
      const sourceJson = resume?.parsed_json || {};
      const copy = await createResume(sourceJson);
      showToast({ type: "success", message: "Resume duplicated." });
      return copy;
    },
    [createResume, showToast],
  );

  const generateSummary = useCallback(
    async (resumeId, parsedJson) => {
      try {
        const response = await api.post(`/resumes/${resumeId}/generate-summary`, {
          parsed_json: parsedJson,
        });
        return response.data;
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Summary generation failed." });
        throw error;
      }
    },
    [showToast],
  );

  const downloadResume = useCallback(
    async (resumeId, kind = "pdf", templateId = "", filenameBase = "") => {
      const path = kind === "pdf" ? "export-pdf" : "export-docx";
      const fileExt = kind === "pdf" ? "pdf" : "docx";
      const qp = templateId ? `?template_id=${encodeURIComponent(templateId)}` : "";
      const base = String(filenameBase || `resume-${resumeId}`).replace(/\.(pdf|docx|tex)$/i, "");
      try {
        const response = await api.get(`/resumes/${resumeId}/${path}${qp}`, { responseType: "blob" });
        triggerFileDownload(response.data, `${base}.${fileExt}`);
        if (kind === "pdf") {
          const h = response.headers;
          const renderMode = String(
            (typeof h?.get === "function" ? h.get("x-resumeiq-render-mode") : h?.["x-resumeiq-render-mode"]) || "",
          ).toLowerCase();
          if (renderMode === "reportlab_fallback" && !window.sessionStorage.getItem(PDF_FALLBACK_WARN_KEY)) {
            window.sessionStorage.setItem(PDF_FALLBACK_WARN_KEY, "1");
            showToast({
              type: "info",
              message: "PDF downloaded with the structured resume layout.",
            });
          } else if (renderMode && renderMode !== "latex" && !window.sessionStorage.getItem(PDF_FALLBACK_WARN_KEY)) {
            window.sessionStorage.setItem(PDF_FALLBACK_WARN_KEY, "1");
            showToast({
              type: "info",
              message: "PDF downloaded successfully.",
            });
          }
        }
      } catch (error) {
        const status = error.response?.status;
        if (kind === "pdf" && status === 503) {
          const msg = await detailMessageFromAxiosError(error, "PDF could not be generated. Please try again.");
          showToast({ type: "error", message: msg });
          throw error;
        }
        if (kind !== "pdf") {
          try {
            const fallback = await api.get(`/resumes/${resumeId}/export-tex${qp}`, { responseType: "blob" });
            triggerFileDownload(fallback.data, `${base}.tex`);
            showToast({
              type: "warning",
              message: "DOCX export is unavailable on this backend. Downloaded TEX source instead.",
            });
            return;
          } catch {
            // continue with original error
          }
        }

        const errMsg = await detailMessageFromAxiosError(error, "Download failed.");
        showToast({ type: "error", message: errMsg });
        throw error;
      }
    },
    [showToast],
  );

  return {
    resumes,
    loading,
    fetchResumes,
    createResume,
    updateResume,
    getResume,
    deleteResume,
    duplicateResume,
    generateSummary,
    downloadResume,
  };
}
