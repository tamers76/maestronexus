/**
 * Typed helpers for the AI module (tutor + content drafts).
 *
 * Mirrors `backend/app/modules/ai` (docs/06, docs/07). The content-draft helpers
 * are exported here so the content/admin agent can integrate the review UI
 * without duplicating types.
 */

import { apiFetch } from "@/lib/api";

// ── Tutor ─────────────────────────────────────────────────────────────────────

export type TutorSource = {
  content_item_id: string;
  node_id: string;
  title: string;
  snippet: string;
};

export type TutorRequest = {
  question: string;
  node_id?: string | null;
  course_id?: string | null;
  assessment_id?: string | null;
};

export type TutorResponse = {
  interaction_id: string;
  answer: string;
  grounded: boolean;
  refused: boolean;
  escalate: boolean;
  escalation_path: string;
  sources: TutorSource[];
  provider: string;
  model: string;
  stubbed: boolean;
};

export function askTutor(req: TutorRequest): Promise<TutorResponse> {
  return apiFetch<TutorResponse>("/ai/tutor", { method: "POST", json: req });
}

// ── Content drafts ─────────────────────────────────────────────────────────────

export type DraftCreate = {
  topic: string;
  title?: string | null;
  modality?: string;
  objectives?: string[];
  node_id?: string | null;
  instructions?: string | null;
};

export type ContentDraftBody = {
  title?: string;
  modality?: string;
  format?: string;
  body?: string;
  topic?: string;
  objectives?: string[];
  node_id?: string | null;
  provider?: string;
  model?: string;
  stubbed?: boolean;
  [key: string]: unknown;
};

export type ContentDraft = {
  id: string;
  interaction_id: string | null;
  target_type: string;
  review_status: "pending" | "approved" | string;
  draft: ContentDraftBody;
  created_at: string;
  updated_at: string;
};

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export function generateContentDraft(req: DraftCreate): Promise<ContentDraft> {
  return apiFetch<ContentDraft>("/ai/content/draft", {
    method: "POST",
    json: req,
  });
}

export function listContentDrafts(params?: {
  reviewStatus?: string;
  limit?: number;
  offset?: number;
}): Promise<Page<ContentDraft>> {
  const search = new URLSearchParams();
  if (params?.reviewStatus) search.set("review_status", params.reviewStatus);
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.offset != null) search.set("offset", String(params.offset));
  const qs = search.toString();
  return apiFetch<Page<ContentDraft>>(`/ai/content/draft${qs ? `?${qs}` : ""}`);
}

export function approveContentDraft(id: string): Promise<ContentDraft> {
  return apiFetch<ContentDraft>(`/ai/content/draft/${id}/approve`, {
    method: "POST",
  });
}
