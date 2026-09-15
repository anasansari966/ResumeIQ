import { useCallback, useState } from "react";
import api from "../api";
import { useToast } from "../components/Toast";

export default function useJobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchMeta, setSearchMeta] = useState({
    suggestedRoles: [],
    queriesUsed: [],
    message: "",
    experienceYears: null,
    experiencePhrase: "",
  });
  const { showToast } = useToast();

  const searchJobs = useCallback(
    async ({ q = "", location = "", source = "", resumeId = "" } = {}) => {
      setLoading(true);
      try {
        const response = await api.get("/jobs/search", {
          params: {
            q,
            location,
            source: source || undefined,
            resume_id: resumeId || undefined,
          },
        });
        const rows = response.data || [];
        setJobs(rows);
        return rows;
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Failed to fetch jobs." });
        return [];
      } finally {
        setLoading(false);
      }
    },
    [showToast],
  );

  const matchJobs = useCallback(
    async ({ resumeId = "", source = "" } = {}) => {
      setLoading(true);
      try {
        const response = await api.get("/jobs/match", {
          params: {
            resume_id: resumeId || undefined,
            source: source || undefined,
          },
        });
        const rows = response.data || [];
        setJobs(rows);
        return rows;
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Failed to fetch job recommendations." });
        return [];
      } finally {
        setLoading(false);
      }
    },
    [showToast],
  );

  const smartSearch = useCallback(
    async ({ resumeId, query = "", location = "", workType = "all", datePosted = "all" } = {}) => {
      if (!resumeId) {
        setJobs([]);
        setSearchMeta((prev) => ({ ...prev, message: "Upload or select a resume to find eligible jobs." }));
        return { jobs: [], suggested_roles: [] };
      }
      setLoading(true);
      try {
        const response = await api.post(
          "/jobs/jsearch/smart",
          {
            resume_id: Number(resumeId),
            manual_query: query,
            location,
            work_type: workType,
            date_posted: datePosted,
            page: 1,
            num_pages: 2,
          },
          { timeout: 240000 },
        );
        const data = response.data || {};
        const rows = (data.jobs || []).filter((job) => job.is_eligible !== false);
        setJobs(rows);
        setSearchMeta({
          suggestedRoles: data.suggested_roles || [],
          queriesUsed: data.queries_used || [],
          message: data.message || "Resume analysis complete.",
          experienceYears: data.experience_years_used ?? null,
          experiencePhrase: data.experience_phrase || "",
        });
        return { ...data, jobs: rows };
      } catch (error) {
        const message = error.response?.data?.detail || "Could not search for resume-matched jobs.";
        setJobs([]);
        setSearchMeta((prev) => ({ ...prev, message }));
        showToast({ type: "error", message });
        return { jobs: [], suggested_roles: [] };
      } finally {
        setLoading(false);
      }
    },
    [showToast],
  );

  const refreshDescription = useCallback(
    async (jobId, resumeId = "") => {
      try {
        const response = await api.post(`/jobs/listing/${jobId}/refresh-description`, null, {
          params: { resume_id: resumeId || undefined },
        });
        const updated = response.data;
        setJobs((prev) => prev.map((job) => (job.id === updated.id ? updated : job)));
        return updated;
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Could not refresh description." });
        throw error;
      }
    },
    [showToast],
  );

  return {
    jobs,
    loading,
    searchJobs,
    matchJobs,
    smartSearch,
    searchMeta,
    refreshDescription,
    setJobs,
  };
}
