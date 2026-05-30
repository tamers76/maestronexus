/**
 * Typed client for Maestro Studio — the 18-stage Blueprint features
 * (`/api/v1/stages`).
 *
 * Mirrors `backend/app/modules/stages`. Each stage is a re-runnable step of the
 * Blueprint curriculum re-engineering flow on a course; runs execute in single
 * or council mode, are scored for risk, and route to an SME for approval when
 * flagged. Approving a run promotes its structured artifact into domain state
 * (the `promotes_to` target).
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
  /** Legacy stage_key aliases that resolve to this canonical stage. */
  aliases: string[];
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
  aliases: string[];
  last_run: StageRunSummary | null;
};

/** The current approved design artifact for a stage on a course. */
export type ApprovedArtifact = {
  stage_key: string;
  source: "design_artifact" | "stage_run" | string;
  review_status: string;
  course_version_id: string | null;
  source_run_id: string | null;
  artifact: unknown | null;
  updated_at: string;
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

/** Current approved design artifact for a stage (or null if none approved). */
export function getApprovedArtifact(
  courseId: string,
  stageKey: string,
): Promise<ApprovedArtifact | null> {
  return apiFetch<ApprovedArtifact | null>(
    `/stages/courses/${courseId}/stages/${stageKey}/approved`,
  );
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
