/**
 * Typed client for the enrollment & progress API (docs/05, docs/12).
 *
 * Backed by `apiFetch` (auth + error envelope). Mirrors the FastAPI schemas in
 * `backend/app/modules/enrollment/schemas.py`.
 */

import { apiFetch } from "@/lib/api";

export type NodeState = "locked" | "available" | "completed" | "mastered";

export type ClassOut = {
  id: string;
  tenant_id: string;
  course_id: string;
  teacher_id: string | null;
  name: string;
  created_at: string;
};

export type CourseVersionOut = {
  id: string;
  version: number;
  state: string;
};

export type CourseOut = {
  id: string;
  title: string;
  status: string;
  versions: CourseVersionOut[];
};

export type EnrollmentOut = {
  id: string;
  tenant_id: string;
  user_id: string;
  class_id: string;
  course_version_id: string;
  status: string;
  created_at: string;
};

export type NodeProgressOut = {
  id: string;
  node_id: string;
  node_title: string;
  node_type: string;
  state: NodeState;
  attempts: number;
  time_spent_seconds: number;
  confidence: number | null;
  completed_at: string | null;
};

export type NodeEdgeOut = {
  source_node_id: string;
  target_node_id: string;
  dependency_type: string;
};

export type EnrollmentDetail = {
  enrollment: EnrollmentOut;
  class_name: string;
  learner_name: string;
  nodes: NodeProgressOut[];
  edges: NodeEdgeOut[];
};

export type CompleteNodeResult = {
  node: NodeProgressOut;
  unlocked_node_ids: string[];
  mastered: boolean;
};

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

// ── Courses (pickers) ────────────────────────────────────────────────────────

export function listCourses(): Promise<CourseOut[]> {
  return apiFetch<CourseOut[]>("/enrollment/courses");
}

// ── Classes ──────────────────────────────────────────────────────────────────

export function listClasses(teacherId?: string): Promise<Page<ClassOut>> {
  const q = teacherId ? `?teacher_id=${encodeURIComponent(teacherId)}` : "";
  return apiFetch<Page<ClassOut>>(`/enrollment/classes${q}`);
}

export function getClass(classId: string): Promise<ClassOut> {
  return apiFetch<ClassOut>(`/enrollment/classes/${classId}`);
}

export function createClass(input: {
  course_id: string;
  name: string;
  teacher_id?: string | null;
}): Promise<ClassOut> {
  return apiFetch<ClassOut>("/enrollment/classes", { method: "POST", json: input });
}

export function updateClass(
  classId: string,
  input: { name?: string; teacher_id?: string | null },
): Promise<ClassOut> {
  return apiFetch<ClassOut>(`/enrollment/classes/${classId}`, {
    method: "PATCH",
    json: input,
  });
}

// ── Enrollments ──────────────────────────────────────────────────────────────

export function enrollLearner(input: {
  class_id: string;
  email?: string;
  user_id?: string;
  course_version_id?: string | null;
}): Promise<EnrollmentOut> {
  return apiFetch<EnrollmentOut>("/enrollment/enrollments", {
    method: "POST",
    json: input,
  });
}

export function listEnrollments(params: {
  class_id?: string;
  user_id?: string;
}): Promise<Page<EnrollmentOut>> {
  const search = new URLSearchParams();
  if (params.class_id) search.set("class_id", params.class_id);
  if (params.user_id) search.set("user_id", params.user_id);
  const q = search.toString();
  return apiFetch<Page<EnrollmentOut>>(`/enrollment/enrollments${q ? `?${q}` : ""}`);
}

export function myEnrollments(): Promise<EnrollmentOut[]> {
  return apiFetch<EnrollmentOut[]>("/enrollment/me/enrollments");
}

export function getEnrollmentDetail(enrollmentId: string): Promise<EnrollmentDetail> {
  return apiFetch<EnrollmentDetail>(`/enrollment/enrollments/${enrollmentId}`);
}

export function completeNode(
  enrollmentId: string,
  nodeId: string,
  input: { score?: number | null; time_spent_seconds?: number; confidence?: number | null } = {},
): Promise<CompleteNodeResult> {
  return apiFetch<CompleteNodeResult>(
    `/enrollment/enrollments/${enrollmentId}/nodes/${nodeId}/complete`,
    { method: "POST", json: { time_spent_seconds: 0, ...input } },
  );
}
