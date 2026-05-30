/**
 * Typed API helpers for the Courses & Learning Graph vertical (docs/04, docs/13).
 *
 * Mirrors the backend surface under `/api/v1/courses`: courses, versions,
 * learning nodes, dependencies (edges), and the React-Flow graph projection.
 */

import { apiFetch } from "@/lib/api";

// ── Shared types ─────────────────────────────────────────────────────────────

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type DependencyType = "requires" | "mastery_gate";

export type XYPosition = { x: number; y: number };

// ── Courses ──────────────────────────────────────────────────────────────────

export type Course = {
  id: string;
  tenant_id: string;
  program_id: string | null;
  title: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CourseCreate = {
  title: string;
  description?: string | null;
  program_id?: string | null;
};

export type CourseUpdate = {
  title?: string;
  description?: string | null;
  status?: string;
};

export function listCourses(limit = 50, offset = 0): Promise<Page<Course>> {
  return apiFetch<Page<Course>>(`/courses?limit=${limit}&offset=${offset}`);
}

export function getCourse(courseId: string): Promise<Course> {
  return apiFetch<Course>(`/courses/${courseId}`);
}

export function createCourse(payload: CourseCreate): Promise<Course> {
  return apiFetch<Course>("/courses", { method: "POST", json: payload });
}

export function updateCourse(courseId: string, payload: CourseUpdate): Promise<Course> {
  return apiFetch<Course>(`/courses/${courseId}`, { method: "PATCH", json: payload });
}

export function deleteCourse(courseId: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/courses/${courseId}`, { method: "DELETE" });
}

// ── Course versions ──────────────────────────────────────────────────────────

export type CourseVersion = {
  id: string;
  course_id: string;
  version: number;
  state: string;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export function listVersions(courseId: string): Promise<CourseVersion[]> {
  return apiFetch<CourseVersion[]>(`/courses/${courseId}/versions`);
}

export function getVersion(versionId: string): Promise<CourseVersion> {
  return apiFetch<CourseVersion>(`/courses/versions/${versionId}`);
}

export function createVersion(
  courseId: string,
  cloneFromLatest = true,
): Promise<CourseVersion> {
  return apiFetch<CourseVersion>(`/courses/${courseId}/versions`, {
    method: "POST",
    json: { clone_from_latest: cloneFromLatest },
  });
}

export function publishVersion(versionId: string): Promise<CourseVersion> {
  return apiFetch<CourseVersion>(`/courses/versions/${versionId}/publish`, {
    method: "POST",
  });
}

// ── Learning nodes ───────────────────────────────────────────────────────────

export type LearningNode = {
  id: string;
  course_version_id: string;
  type: string;
  title: string;
  learning_objective: Record<string, unknown>;
  mastery_rule: Record<string, unknown>;
  completion_rule: Record<string, unknown>;
  estimated_duration: number | null;
  position: XYPosition;
  node_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type LearningNodeCreate = {
  title: string;
  type?: string;
  learning_objective?: Record<string, unknown>;
  mastery_rule?: Record<string, unknown>;
  completion_rule?: Record<string, unknown>;
  estimated_duration?: number | null;
  position?: XYPosition;
};

export type LearningNodeUpdate = {
  title?: string;
  type?: string;
  learning_objective?: Record<string, unknown>;
  mastery_rule?: Record<string, unknown>;
  completion_rule?: Record<string, unknown>;
  estimated_duration?: number | null;
  position?: XYPosition;
};

export function listNodes(versionId: string): Promise<LearningNode[]> {
  return apiFetch<LearningNode[]>(`/courses/versions/${versionId}/nodes`);
}

export function createNode(
  versionId: string,
  payload: LearningNodeCreate,
): Promise<LearningNode> {
  return apiFetch<LearningNode>(`/courses/versions/${versionId}/nodes`, {
    method: "POST",
    json: payload,
  });
}

export function updateNode(
  nodeId: string,
  payload: LearningNodeUpdate,
): Promise<LearningNode> {
  return apiFetch<LearningNode>(`/courses/nodes/${nodeId}`, {
    method: "PATCH",
    json: payload,
  });
}

export function deleteNode(nodeId: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/courses/nodes/${nodeId}`, { method: "DELETE" });
}

// ── Node dependencies (edges) ─────────────────────────────────────────────────

export type NodeDependency = {
  id: string;
  source_node_id: string;
  target_node_id: string;
  dependency_type: string;
};

export type NodeDependencyCreate = {
  source_node_id: string;
  target_node_id: string;
  dependency_type: DependencyType;
};

export function createDependency(
  versionId: string,
  payload: NodeDependencyCreate,
): Promise<NodeDependency> {
  return apiFetch<NodeDependency>(`/courses/versions/${versionId}/dependencies`, {
    method: "POST",
    json: payload,
  });
}

export function deleteDependency(dependencyId: string): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/courses/dependencies/${dependencyId}`, {
    method: "DELETE",
  });
}

// ── Graph projection (React Flow) ──────────────────────────────────────────────

export type GraphNode = {
  id: string;
  type: string;
  position: XYPosition;
  data: {
    label: string;
    nodeType: string;
    estimatedDuration: number | null;
    learningObjective: Record<string, unknown>;
    masteryRule: Record<string, unknown>;
    completionRule: Record<string, unknown>;
  };
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string | null;
  data: { dependencyType: DependencyType };
};

export type GraphResponse = {
  version: CourseVersion;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export function getGraph(versionId: string): Promise<GraphResponse> {
  return apiFetch<GraphResponse>(`/courses/versions/${versionId}/graph`);
}

// ── Node taxonomy (docs/04) ────────────────────────────────────────────────────

export const NODE_TYPES: { value: string; label: string }[] = [
  { value: "lesson", label: "Lesson" },
  { value: "concept", label: "Concept" },
  { value: "micro_lesson", label: "Micro-lesson" },
  { value: "video", label: "Video" },
  { value: "reading", label: "Reading" },
  { value: "quiz", label: "Quiz" },
  { value: "assignment", label: "Assignment" },
  { value: "project", label: "Project" },
  { value: "practice", label: "Practice" },
  { value: "lab", label: "Lab" },
  { value: "assessment", label: "Assessment" },
  { value: "mastery_checkpoint", label: "Mastery checkpoint" },
  { value: "remediation", label: "Remediation" },
  { value: "enrichment", label: "Enrichment" },
];
