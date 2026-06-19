/**
 * Typed client for the runtime AI Settings control center
 * (`/api/v1/integrations/ai-settings`).
 *
 * Mirrors `backend/app/modules/integrations`. This is the admin's single place to
 * control API keys, the LLM Council defaults, and per-stage configuration
 * (execution mode, models, and member/chairman prompts). Secrets are always
 * returned masked; only non-masked values are persisted on update.
 */

import { apiFetch } from "@/lib/api";

// ── Config shapes (the JSONB blob, as the UI sees it) ───────────────────────

export type ProviderConfig = {
  api_key?: string;
  base_url?: string;
  /** Read-only flag from the server: a secret is stored for this provider. */
  configured?: boolean;
};

export type CouncilDefaults = {
  members?: string[];
  chairman?: string;
  member_system_prompt?: string;
  chairman_system_prompt?: string;
};

export type StageConfig = {
  mode?: "single" | "council";
  single_model?: string;
  council_models?: string[];
  chairman_model?: string;
  member_system_prompt?: string;
  chairman_system_prompt?: string;
};

export type AiConfig = {
  providers?: Record<string, ProviderConfig>;
  council?: CouncilDefaults;
  stages?: Record<string, StageConfig>;
};

export type StageCatalogEntry = {
  key: string;
  order: number;
  title: string;
  description: string;
  risk: "low" | "high" | string;
  default_execution: "single" | "council" | string;
};

export type ResolvedStage = {
  stage_key: string;
  mode: string;
  provider: string;
  single_model: string;
  council_models: string[];
  chairman_model: string;
  member_system_prompt: string;
  chairman_system_prompt: string;
  uses_defaults: boolean;
};

export type AiSettingsResponse = {
  config: AiConfig;
  catalog: StageCatalogEntry[];
  resolved: ResolvedStage[];
  recommended_prompts: Record<
    string,
    { member_system_prompt: string; chairman_system_prompt: string }
  >;
  managed_providers: string[];
};

export type AiSettingsUpdate = {
  providers?: Record<string, ProviderConfig>;
  council?: CouncilDefaults;
  stages?: Record<string, StageConfig>;
};

export type TestConnectionResult = {
  success: boolean;
  message: string;
  /** True when a freshly typed key was saved to the tenant store after testing. */
  persisted?: boolean;
};
export type ModelOption = { id: string; name: string };

const BASE = "/integrations/ai-settings";

export function getAiSettings(): Promise<AiSettingsResponse> {
  return apiFetch<AiSettingsResponse>(BASE);
}

export function updateAiSettings(patch: AiSettingsUpdate): Promise<AiSettingsResponse> {
  return apiFetch<AiSettingsResponse>(BASE, { method: "PUT", json: patch });
}

export function testConnection(
  provider: string,
  creds?: { api_key?: string; base_url?: string },
): Promise<TestConnectionResult> {
  return apiFetch<TestConnectionResult>(`${BASE}/test-connection`, {
    method: "POST",
    json: { provider, api_key: creds?.api_key, base_url: creds?.base_url },
  });
}

export function listProviderModels(provider = "openai"): Promise<ModelOption[]> {
  return apiFetch<ModelOption[]>(`${BASE}/models?provider=${encodeURIComponent(provider)}`);
}

export function resetStagePrompts(stageKey: string): Promise<AiSettingsResponse> {
  return apiFetch<AiSettingsResponse>(`${BASE}/stages/${stageKey}/reset-prompts`, {
    method: "POST",
  });
}
