import { useEffect, useState } from "react";
import { fetchProjects } from "../services/api";
import type { Project } from "../types";

export function useProject() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    fetchProjects()
      .then(setProjects)
      .catch((err) => setError(err instanceof Error ? err : new Error(String(err))))
      .finally(() => setLoading(false));
  }, []);

  return { projects, loading, error, refresh: () => fetchProjects().then(setProjects) };
}
