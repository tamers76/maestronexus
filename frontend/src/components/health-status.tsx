"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { API_BASE_URL, type ReadinessResponse, fetchReadiness } from "@/lib/api";

const SERVICE_LABELS: Record<string, string> = {
  postgres: "PostgreSQL",
  redis: "Redis",
  storage: "MinIO / S3",
};

const UNREACHABLE = `Backend unreachable at ${API_BASE_URL}. Is uvicorn running?`;

export function HealthStatus() {
  const [data, setData] = useState<ReadinessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Initial load: state is only updated inside the async callbacks (never
  // synchronously in the effect body), per react-hooks/set-state-in-effect.
  useEffect(() => {
    let active = true;
    fetchReadiness()
      .then((res) => {
        if (active) setData(res);
      })
      .catch(() => {
        if (active) setError(UNREACHABLE);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchReadiness());
    } catch {
      setData(null);
      setError(UNREACHABLE);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="w-full max-w-md rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Backend services
        </h2>
        <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>
          {loading ? "Checking…" : "Recheck"}
        </Button>
      </div>

      {error ? (
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      ) : (
        <ul className="space-y-2">
          {data
            ? Object.entries(data.checks).map(([key, check]) => (
                <li
                  key={key}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-zinc-700 dark:text-zinc-300">
                    {SERVICE_LABELS[key] ?? key}
                  </span>
                  <span
                    className={
                      check.ok
                        ? "inline-flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400"
                        : "inline-flex items-center gap-1.5 font-medium text-red-600 dark:text-red-400"
                    }
                  >
                    <span
                      className={
                        check.ok
                          ? "h-2 w-2 rounded-full bg-emerald-500"
                          : "h-2 w-2 rounded-full bg-red-500"
                      }
                    />
                    {check.ok ? "healthy" : "down"}
                  </span>
                </li>
              ))
            : !loading && <li className="text-sm text-zinc-500">No data.</li>}
        </ul>
      )}
    </div>
  );
}
