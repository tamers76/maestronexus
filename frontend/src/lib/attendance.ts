/**
 * Typed helpers for the attendance API (docs/09).
 *
 * Sessions + per-learner records are class-scoped: the backend only returns
 * data for classes the caller teaches. All requests go through `apiFetch`.
 */

import { apiFetch } from "@/lib/api";

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type PageQuery = { limit?: number; offset?: number };

export type AttendanceStatus = "present" | "absent" | "late" | "excused";
export type SessionMode = "in_person" | "online" | "hybrid";

function qs(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ── Types ──────────────────────────────────────────────────────────────────

export type ClassInfo = {
  id: string;
  name: string;
  course_id: string;
};

export type AttendanceSession = {
  id: string;
  tenant_id: string;
  class_id: string;
  scheduled_at: string;
  mode: string;
  created_at: string;
  updated_at: string;
};

export type AttendanceRecord = {
  id: string;
  session_id: string;
  learner_id: string;
  status: string;
  marked_at: string | null;
  marked_by: string | null;
  created_at: string;
  updated_at: string;
};

export type RosterEntry = {
  learner_id: string;
  display_name: string;
  email: string;
  status: string | null;
  marked_at: string | null;
};

// ── Classes (selection helper) ───────────────────────────────────────────────

export function listClasses(): Promise<ClassInfo[]> {
  return apiFetch<ClassInfo[]>("/attendance/classes");
}

// ── Sessions ─────────────────────────────────────────────────────────────────

export function createSession(data: {
  class_id: string;
  scheduled_at: string;
  mode?: SessionMode;
}): Promise<AttendanceSession> {
  return apiFetch<AttendanceSession>("/attendance/sessions", {
    method: "POST",
    json: data,
  });
}

export function listSessions(
  params: PageQuery & { class_id?: string } = {},
): Promise<Page<AttendanceSession>> {
  return apiFetch<Page<AttendanceSession>>(`/attendance/sessions${qs(params)}`);
}

export function getSession(sessionId: string): Promise<AttendanceSession> {
  return apiFetch<AttendanceSession>(`/attendance/sessions/${sessionId}`);
}

// ── Roster + records ─────────────────────────────────────────────────────────

export function getRoster(sessionId: string): Promise<RosterEntry[]> {
  return apiFetch<RosterEntry[]>(`/attendance/sessions/${sessionId}/roster`);
}

export function listRecords(sessionId: string): Promise<AttendanceRecord[]> {
  return apiFetch<AttendanceRecord[]>(`/attendance/sessions/${sessionId}/records`);
}

export function markRecords(
  sessionId: string,
  records: { learner_id: string; status: AttendanceStatus }[],
): Promise<AttendanceRecord[]> {
  return apiFetch<AttendanceRecord[]>(`/attendance/sessions/${sessionId}/records`, {
    method: "POST",
    json: { records },
  });
}
