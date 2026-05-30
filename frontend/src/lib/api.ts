export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type HealthCheck = { ok: boolean; detail: string };

export type ReadinessResponse = {
  status: "ready" | "degraded";
  checks: Record<string, HealthCheck>;
};

export async function fetchReadiness(): Promise<ReadinessResponse> {
  const res = await fetch(`${API_BASE_URL}/health/ready`, { cache: "no-store" });
  return (await res.json()) as ReadinessResponse;
}
