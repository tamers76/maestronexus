/**
 * Typed helpers for the projects API (docs/08).
 *
 * Covers project + rubric management, per-learner submissions, and the
 * object-scoped teacher grading queue. All requests go through `apiFetch`,
 * which handles auth + the JSON error envelope.
 */

import { apiFetch } from "@/lib/api";

// ── Shared ───────────────────────────────────────────────────────────────────

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type PageQuery = { limit?: number; offset?: number };

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

export type Project = {
  id: string;
  node_id: string;
  title: string;
  instructions: Record<string, unknown>;
  collaborative: boolean;
  max_submissions: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type Rubric = {
  id: string;
  project_id: string;
  criteria: RubricCriteria;
  created_at: string;
  updated_at: string;
};

/** Flexible rubric shape the grading UI understands (criteria.items). */
export type RubricCriteria = {
  items?: RubricCriterion[];
  [key: string]: unknown;
};

export type RubricCriterion = {
  key: string;
  label: string;
  max?: number;
  weight?: number;
};

export type Submission = {
  id: string;
  project_id: string;
  learner_id: string;
  attempt_no: number;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type SubmissionListItem = {
  id: string;
  project_id: string;
  project_title: string;
  learner_id: string;
  learner_name: string;
  class_id: string;
  class_name: string;
  attempt_no: number;
  status: string;
  graded: boolean;
  score: number | null;
  created_at: string;
};

export type Grade = {
  id: string;
  submission_id: string;
  grader_id: string | null;
  score: number | null;
  rubric_scores: Record<string, number>;
  created_at: string;
  updated_at: string;
};

export type Feedback = {
  id: string;
  grade_id: string;
  author_type: string;
  body: string;
  created_at: string;
  updated_at: string;
};

export type SubmissionDetail = {
  submission: Submission;
  project: Project;
  learner_name: string;
  class_id: string;
  class_name: string;
  rubric: Rubric | null;
  grade: Grade | null;
  feedback: Feedback | null;
};

export type GradeInput = {
  score?: number | null;
  rubric_scores?: Record<string, number>;
  feedback?: string;
};

export type GradeResult = { grade: Grade; feedback: Feedback | null };

// ── Project + rubric management (project.grade) ──────────────────────────────

export function createProject(data: {
  node_id: string;
  title: string;
  instructions?: Record<string, unknown>;
  collaborative?: boolean;
  max_submissions?: number;
}): Promise<Project> {
  return apiFetch<Project>("/projects", { method: "POST", json: data });
}

export function listProjects(
  params: PageQuery & { node_id?: string } = {},
): Promise<Page<Project>> {
  return apiFetch<Page<Project>>(`/projects${qs(params)}`);
}

export function getProject(projectId: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`);
}

export function updateProject(
  projectId: string,
  data: Partial<{
    title: string;
    instructions: Record<string, unknown>;
    collaborative: boolean;
    max_submissions: number;
  }>,
): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`, { method: "PATCH", json: data });
}

export function deleteProject(projectId: string): Promise<void> {
  return apiFetch<void>(`/projects/${projectId}`, { method: "DELETE" });
}

export function setRubric(projectId: string, criteria: RubricCriteria): Promise<Rubric> {
  return apiFetch<Rubric>(`/projects/${projectId}/rubric`, {
    method: "PUT",
    json: { criteria },
  });
}

export function getRubric(projectId: string): Promise<Rubric | null> {
  return apiFetch<Rubric | null>(`/projects/${projectId}/rubric`);
}

// ── Teacher grading queue (project.grade, own classes) ───────────────────────

export function listGradingQueue(
  params: PageQuery & { class_id?: string } = {},
): Promise<Page<SubmissionListItem>> {
  return apiFetch<Page<SubmissionListItem>>(`/projects/submissions${qs(params)}`);
}

export function getSubmissionDetail(submissionId: string): Promise<SubmissionDetail> {
  return apiFetch<SubmissionDetail>(`/projects/submissions/${submissionId}`);
}

export function gradeSubmission(
  submissionId: string,
  input: GradeInput,
): Promise<GradeResult> {
  return apiFetch<GradeResult>(`/projects/submissions/${submissionId}/grade`, {
    method: "POST",
    json: input,
  });
}

// ── Learner submissions (project.submit, own work) ───────────────────────────

export function submitProject(
  projectId: string,
  payload: Record<string, unknown>,
): Promise<Submission> {
  return apiFetch<Submission>(`/projects/${projectId}/submissions`, {
    method: "POST",
    json: { payload },
  });
}

export function listMySubmissions(projectId: string): Promise<Submission[]> {
  return apiFetch<Submission[]>(`/projects/${projectId}/submissions/mine`);
}
