/**
 * Typed client for the Content & Assessment API (`/api/v1/content`).
 *
 * Mirrors the backend schemas (docs/07, docs/13). Authoring helpers carry full
 * data (including `answer_key`); learner helpers map to the answer-key-stripped
 * endpoints. Built on the shared `apiFetch` so auth + error envelopes are handled.
 */

import { apiFetch } from "@/lib/api";

// ── Shared types ─────────────────────────────────────────────────────────────

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type ApprovalStatus = "draft" | "in_review" | "approved" | "archived";

export type ContentItem = {
  id: string;
  node_id: string;
  modality: string;
  version: number;
  body: Record<string, unknown>;
  approval_status: ApprovalStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type MediaAsset = {
  id: string;
  storage_key: string;
  mime_type: string;
  size_bytes: number;
  content_item_id: string | null;
  created_at: string;
};

export type MediaDownload = { asset: MediaAsset; download_url: string };

export type Assessment = {
  id: string;
  node_id: string;
  type: string;
  config: Record<string, unknown>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type Question = {
  id: string;
  assessment_id: string;
  type: string;
  prompt: Record<string, unknown>;
  answer_key: Record<string, unknown>;
  position: number;
};

/** Learner-facing question — note: no `answer_key`. */
export type LearnerQuestion = Omit<Question, "answer_key">;

export type AssessmentDetail = Assessment & { questions: Question[] };
export type LearnerAssessment = {
  id: string;
  node_id: string;
  type: string;
  config: Record<string, unknown>;
  questions: LearnerQuestion[];
};

export type Attempt = {
  id: string;
  enrollment_id: string;
  assessment_id: string;
  score: number | null;
  responses: Record<string, unknown>;
  submitted_at: string | null;
};

// ── Content items ──────────────────────────────────────────────────────────

export function listContentItems(
  nodeId: string,
  opts: { approvalStatus?: ApprovalStatus; limit?: number; offset?: number } = {},
): Promise<Page<ContentItem>> {
  const params = new URLSearchParams({ node_id: nodeId });
  if (opts.approvalStatus) params.set("approval_status", opts.approvalStatus);
  if (opts.limit != null) params.set("limit", String(opts.limit));
  if (opts.offset != null) params.set("offset", String(opts.offset));
  return apiFetch<Page<ContentItem>>(`/content/items?${params.toString()}`);
}

export function listLearnerContent(nodeId: string): Promise<Page<ContentItem>> {
  const params = new URLSearchParams({ node_id: nodeId });
  return apiFetch<Page<ContentItem>>(`/content/learner/items?${params.toString()}`);
}

export function getContentItem(id: string): Promise<ContentItem> {
  return apiFetch<ContentItem>(`/content/items/${id}`);
}

export function createContentItem(input: {
  node_id: string;
  modality: string;
  body: Record<string, unknown>;
  version?: number;
}): Promise<ContentItem> {
  return apiFetch<ContentItem>("/content/items", { method: "POST", json: input });
}

export function updateContentItem(
  id: string,
  input: { modality?: string; body?: Record<string, unknown> },
): Promise<ContentItem> {
  return apiFetch<ContentItem>(`/content/items/${id}`, { method: "PATCH", json: input });
}

export function approveContentItem(id: string): Promise<ContentItem> {
  return apiFetch<ContentItem>(`/content/items/${id}/approve`, { method: "POST" });
}

// ── Media ────────────────────────────────────────────────────────────────────

/** Reads a File into a base64 string (no data-URL prefix). */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

export async function uploadMedia(
  file: File,
  contentItemId?: string,
): Promise<MediaAsset> {
  const content_base64 = await fileToBase64(file);
  return apiFetch<MediaAsset>("/content/media", {
    method: "POST",
    json: {
      filename: file.name,
      mime_type: file.type || "application/octet-stream",
      content_base64,
      content_item_id: contentItemId ?? null,
    },
  });
}

export function getMedia(id: string): Promise<MediaDownload> {
  return apiFetch<MediaDownload>(`/content/media/${id}`);
}

// ── Assessments & questions ──────────────────────────────────────────────────

export function listAssessments(nodeId: string): Promise<Page<Assessment>> {
  const params = new URLSearchParams({ node_id: nodeId });
  return apiFetch<Page<Assessment>>(`/content/assessments?${params.toString()}`);
}

export function createAssessment(input: {
  node_id: string;
  type?: string;
  config?: Record<string, unknown>;
}): Promise<Assessment> {
  return apiFetch<Assessment>("/content/assessments", { method: "POST", json: input });
}

export function getAssessment(id: string): Promise<AssessmentDetail> {
  return apiFetch<AssessmentDetail>(`/content/assessments/${id}`);
}

export function getLearnerAssessment(id: string): Promise<LearnerAssessment> {
  return apiFetch<LearnerAssessment>(`/content/learner/assessments/${id}`);
}

export function addQuestion(
  assessmentId: string,
  input: {
    type?: string;
    prompt: Record<string, unknown>;
    answer_key: Record<string, unknown>;
    position?: number;
  },
): Promise<Question> {
  return apiFetch<Question>(`/content/assessments/${assessmentId}/questions`, {
    method: "POST",
    json: input,
  });
}

export function updateQuestion(
  id: string,
  input: {
    type?: string;
    prompt?: Record<string, unknown>;
    answer_key?: Record<string, unknown>;
    position?: number;
  },
): Promise<Question> {
  return apiFetch<Question>(`/content/questions/${id}`, { method: "PATCH", json: input });
}

export function deleteQuestion(id: string): Promise<void> {
  return apiFetch<void>(`/content/questions/${id}`, { method: "DELETE" });
}

// ── Attempts ─────────────────────────────────────────────────────────────────

export function submitAttempt(input: {
  enrollment_id: string;
  assessment_id: string;
  responses: Record<string, unknown>;
}): Promise<Attempt> {
  return apiFetch<Attempt>("/content/attempts", { method: "POST", json: input });
}

export function getAttempt(id: string): Promise<Attempt> {
  return apiFetch<Attempt>(`/content/attempts/${id}`);
}
