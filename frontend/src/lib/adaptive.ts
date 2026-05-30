/**
 * Typed client for the adaptive engine API (docs/05).
 *
 * Mirrors `backend/app/modules/adaptive/schemas.py`. The engine returns the next
 * recommended node with a human-readable `reason`; teacher overrides always win.
 */

import { apiFetch } from "@/lib/api";

export type NextNodeResponse = {
  recommendation_id: string | null;
  recommended_node_id: string | null;
  node_title: string | null;
  node_type: string | null;
  reason: string;
  source: "engine" | "teacher_override" | null;
  course_complete: boolean;
};

export function getNextNode(enrollmentId: string): Promise<NextNodeResponse> {
  return apiFetch<NextNodeResponse>(`/adaptive/enrollments/${enrollmentId}/next-node`);
}

export function overrideNextNode(
  enrollmentId: string,
  input: { node_id: string; reason?: string | null },
): Promise<NextNodeResponse> {
  return apiFetch<NextNodeResponse>(
    `/adaptive/enrollments/${enrollmentId}/next-node/override`,
    { method: "POST", json: input },
  );
}
