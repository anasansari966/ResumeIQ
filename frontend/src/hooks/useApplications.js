import { useCallback, useState } from "react";
import api from "../api";
import { useToast } from "../components/Toast";

export default function useApplications() {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(false);
  const { showToast } = useToast();

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/applications");
      const rows = response.data || [];
      setApplications(rows);
      return rows;
    } catch (error) {
      showToast({ type: "error", message: error.response?.data?.detail || "Failed to fetch applications." });
      return [];
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const createApplication = useCallback(
    async (payload) => {
      try {
        const response = await api.post("/applications", payload);
        await fetchApplications();
        showToast({ type: "success", message: "Application saved." });
        return response.data;
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Could not save application." });
        throw error;
      }
    },
    [fetchApplications, showToast],
  );

  const updateApplication = useCallback(
    async (id, payload) => {
      try {
        const response = await api.patch(`/applications/${id}`, payload);
        setApplications((prev) => prev.map((item) => (item.id === id ? response.data : item)));
        return response.data;
      } catch (error) {
        showToast({ type: "error", message: error.response?.data?.detail || "Could not update application." });
        throw error;
      }
    },
    [showToast],
  );

  return {
    applications,
    loading,
    fetchApplications,
    createApplication,
    updateApplication,
    setApplications,
  };
}
