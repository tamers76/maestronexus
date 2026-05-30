/**
 * Typed client for Maestro Studio — the 12-stage features (`/api/v1/stages`).
 *
 * Mirrors `backend/app/modules/stages`. Each stage is an independent, re-runnable
 * feature on a course; runs execute in single or council mode, are scored for
 * risk, and route to an SME for approval when flagged.
 */

import { apiFetch } from "@/lib/api";

export type StageCatalogItem = {
  key: string;
  order: number;
  title: string;
  description: string;
  inputs: string[];
  output_kind: string;
  default_execution: "single" | "council" | string;
  risk: "low" | "high" | string;
  promotes_to: string | null;
};

export type StageRunSummary = {
  id: string;
  status: string;
  execution_mode: string;
  review_status: string;
  risk_score: number;
  stubbed: boolean;
  created_at: string;
  updated_at: string;
};

export type StageStatus = {
  key: string;
  order: number;
  title: string;
  description: string;
  risk: string;
  default_execution: string;
  promotes_to: string | null;
  last_run: StageRunSummary | null;
};

export type CouncilMember = {
  model: string;
  text: string | null;
  stubbed: boolean;
  error: string | null;
};

export type CouncilTranscript = {
  mode?: string;
  chairman_model?: string;
  members?: CouncilMember[];
};

export type StageRun = {
  id: string;
  course_id: string;
  course_version_id: string | null;
  stage_key: string;
  status: string;
  execution_mode: string;
  input_refs: Record<string, unknown>;
  output: {
    text?: string;
    artifact?: unknown;
    gaps?: unknown[];
    stubbed?: boolean;
    output_kind?: string;
    error?: string;
  };
  council_transcript: CouncilTranscript;
  risk_score: number;
  review_status: string;
  created_at: string;
  updated_at: string;
};

export type RunStageRequest = {
  mode?: "single" | "council";
  course_version_id?: string | null;
  options?: Record<string, unknown>;
};

export function getStageCatalog(): Promise<StageCatalogItem[]> {
  return apiFetch<StageCatalogItem[]>("/stages");
}

export function getCourseStages(courseId: string): Promise<StageStatus[]> {
  return apiFetch<StageStatus[]>(`/stages/courses/${courseId}/stages`);
}

export function runStage(
  courseId: string,
  stageKey: string,
  req: RunStageRequest = {},
): Promise<StageRun> {
  return apiFetch<StageRun>(`/stages/courses/${courseId}/stages/${stageKey}/run`, {
    method: "POST",
    json: req,
  });
}

export function listStageRuns(courseId: string, stageKey?: string): Promise<StageRun[]> {
  const qs = stageKey ? `?stage_key=${encodeURIComponent(stageKey)}` : "";
  return apiFetch<StageRun[]>(`/stages/courses/${courseId}/runs${qs}`);
}

export function getStageRun(runId: string): Promise<StageRun> {
  return apiFetch<StageRun>(`/stages/runs/${runId}`);
}

export function approveStageRun(runId: string, note?: string): Promise<StageRun> {
  return apiFetch<StageRun>(`/stages/runs/${runId}/approve`, {
    method: "POST",
    json: { note: note ?? null },
  });
}

export function rejectStageRun(runId: string, note?: string): Promise<StageRun> {
  return apiFetch<StageRun>(`/stages/runs/${runId}/reject`, {
    method: "POST",
    json: { note: note ?? null },
  });
}
