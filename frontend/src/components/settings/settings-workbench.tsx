"use client";

import { Info, Loader2, Save, Settings2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CouncilDefaultsCard } from "@/components/settings/council-defaults-card";
import { ProviderCard } from "@/components/settings/provider-card";
import { StageConfigTabs } from "@/components/settings/stage-config-tabs";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type AiConfig,
  type AiSettingsResponse,
  type ModelOption,
  type ProviderConfig,
  type ResolvedStage,
  type StageConfig,
  getAiSettings,
  listProviderModels,
  resetStagePrompts,
  updateAiSettings,
} from "@/lib/settings";

export function SettingsWorkbench() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("integration.manage");

  const [data, setData] = useState<AiSettingsResponse | null>(null);
  const [draft, setDraft] = useState<AiConfig>({});
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  // Which provider's live catalog feeds the council/stage model dropdowns.
  const [catalogProvider, setCatalogProvider] = useState("openai");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!canManage) return;
    let active = true;
    (async () => {
      try {
        const resp = await getAiSettings();
        if (!active) return;
        setData(resp);
        setDraft(structuredClone(resp.config));
        // Prefer OpenRouter's catalog when a key is configured (its full
        // provider-namespaced catalog is the richest), else fall back to OpenAI.
        const providers = resp.config.providers ?? {};
        setCatalogProvider(providers.openrouter?.configured ? "openrouter" : "openai");
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load settings.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [canManage]);

  // Load the selected provider's model catalog (re-runs when the source changes).
  useEffect(() => {
    if (!canManage) return;
    let active = true;
    (async () => {
      setModelsLoading(true);
      try {
        const m = await listProviderModels(catalogProvider);
        if (active) setModels(m);
      } catch {
        if (active) setModels([]);
      } finally {
        if (active) setModelsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [canManage, catalogProvider]);

  // Providers whose live catalogs can populate the model dropdowns.
  const catalogProviders = useMemo(
    () =>
      (data?.managed_providers ?? []).filter((p) => p === "openai" || p === "openrouter"),
    [data],
  );

  const serverResolved = useMemo(() => {
    const map: Record<string, ResolvedStage> = {};
    (data?.resolved ?? []).forEach((r) => (map[r.stage_key] = r));
    return map;
  }, [data]);

  // Live resolved preview: server defaults overlaid with the in-progress draft.
  const resolvedMap = useMemo(() => {
    const map: Record<string, ResolvedStage> = {};
    const council = draft.council ?? {};
    (data?.catalog ?? []).forEach((c) => {
      const base = serverResolved[c.key];
      if (!base) return;
      const sc = draft.stages?.[c.key] ?? {};
      const members =
        sc.council_models?.length
          ? sc.council_models
          : council.members?.length
            ? council.members
            : base.council_models;
      map[c.key] = {
        ...base,
        mode: sc.mode ?? base.mode,
        single_model: sc.single_model || base.single_model,
        council_models: members,
        chairman_model: sc.chairman_model || council.chairman || base.chairman_model,
        uses_defaults: Object.keys(sc).length === 0,
      };
    });
    return map;
  }, [data, draft, serverResolved]);

  const setProvider = (name: string, next: ProviderConfig) =>
    setDraft((d) => ({ ...d, providers: { ...(d.providers ?? {}), [name]: next } }));

  const setStage = (key: string, next: StageConfig) =>
    setDraft((d) => ({ ...d, stages: { ...(d.stages ?? {}), [key]: next } }));

  const onSave = async () => {
    setSaving(true);
    setError(null);
    setToast(null);
    try {
      const resp = await updateAiSettings({
        providers: draft.providers,
        council: draft.council,
        stages: draft.stages,
      });
      setData(resp);
      setDraft(structuredClone(resp.config));
      setToast("Settings saved.");
      setTimeout(() => setToast(null), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  const onResetPrompts = async (stageKey: string) => {
    try {
      const resp = await resetStagePrompts(stageKey);
      setData(resp);
      setDraft(structuredClone(resp.config));
      setToast(`Reset ${stageKey} prompts to recommended.`);
      setTimeout(() => setToast(null), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reset prompts.");
    }
  };

  if (!canManage) {
    return (
      <div className="mx-auto w-full max-w-3xl py-10">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Integrations &amp; AI</CardTitle>
            <CardDescription>
              You don&apos;t have permission to manage AI settings.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 py-8">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Settings2 className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Integrations &amp; AI</h1>
            <p className="text-sm text-muted-foreground">
              Control API keys, the LLM Council, and every stage&apos;s models and prompts.
            </p>
          </div>
        </div>
        <Button onClick={onSave} disabled={saving || loading}>
          {saving ? <Loader2 className="animate-spin" /> : <Save />}
          {saving ? "Saving…" : "Save changes"}
        </Button>
      </header>

      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}
      {toast && (
        <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-600 dark:text-emerald-400">
          {toast}
        </p>
      )}

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Providers &amp; API keys</CardTitle>
              <CardDescription>
                Keys are stored per institution and never returned in full. OpenAI and
                OpenRouter run live; other providers fall back to the offline stub until
                wired.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {(data?.managed_providers ?? []).map((p) => (
                <ProviderCard
                  key={p}
                  provider={p}
                  config={draft.providers?.[p] ?? {}}
                  onChange={(next) => setProvider(p, next)}
                />
              ))}
            </CardContent>
          </Card>

          <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" />
            <p>
              <span className="font-medium text-foreground">Single</span> runs one model
              (fast).{" "}
              <span className="font-medium text-foreground">Council</span> asks several
              member models the same task in parallel, then a chairman model synthesizes
              one answer. Set a default below, then tune any of the 12 stages.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/40 p-3 text-sm">
            <Sparkles className="size-4 shrink-0 text-primary" />
            <label htmlFor="catalog-source" className="font-medium text-foreground">
              Model catalog source
            </label>
            <select
              id="catalog-source"
              value={catalogProvider}
              onChange={(e) => setCatalogProvider(e.target.value)}
              className="h-8 rounded-lg border border-border bg-background px-2 text-sm shadow-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {(catalogProviders.length ? catalogProviders : ["openai"]).map((p) => (
                <option key={p} value={p}>
                  {p === "openrouter" ? "OpenRouter" : "OpenAI"}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted-foreground">
              {modelsLoading
                ? "Loading models…"
                : `${models.length} model${models.length === 1 ? "" : "s"} available for the dropdowns below.`}
            </span>
          </div>

          <CouncilDefaultsCard
            council={draft.council ?? {}}
            models={models}
            onChange={(council) => setDraft((d) => ({ ...d, council }))}
          />

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-primary" />
                <CardTitle className="text-base">Per-stage configuration</CardTitle>
              </div>
              <CardDescription>
                The 12 Maestro stages. Each can override the council defaults and its own
                prompts. High-risk stages route runs to an SME for approval.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <StageConfigTabs
                catalog={data?.catalog ?? []}
                stages={draft.stages ?? {}}
                resolved={resolvedMap}
                recommended={data?.recommended_prompts ?? {}}
                models={models}
                onChangeStage={setStage}
                onResetPrompts={onResetPrompts}
              />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
