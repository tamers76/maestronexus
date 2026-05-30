"use client";

import { RotateCcw } from "lucide-react";
import { useState } from "react";

import { ModelMultiSelect, ModelSelect } from "@/components/settings/model-pickers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  ModelOption,
  ResolvedStage,
  StageCatalogEntry,
  StageConfig,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

type Recommended = { member_system_prompt: string; chairman_system_prompt: string };

export function StageConfigTabs({
  catalog,
  stages,
  resolved,
  recommended,
  models,
  onChangeStage,
  onResetPrompts,
}: {
  catalog: StageCatalogEntry[];
  stages: Record<string, StageConfig>;
  resolved: Record<string, ResolvedStage>;
  recommended: Record<string, Recommended>;
  models: ModelOption[];
  onChangeStage: (key: string, next: StageConfig) => void;
  onResetPrompts: (key: string) => void;
}) {
  const [active, setActive] = useState(catalog[0]?.key ?? "");
  const spec = catalog.find((c) => c.key === active);
  const cfg = stages[active] ?? {};
  const res = resolved[active];
  const rec = recommended[active];

  if (!spec) return null;

  const mode = cfg.mode ?? (spec.default_execution as "single" | "council");
  const update = (patch: Partial<StageConfig>) => onChangeStage(active, { ...cfg, ...patch });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
      {/* Stage list */}
      <div className="flex flex-col gap-1">
        {catalog.map((c) => {
          const r = resolved[c.key];
          return (
            <button
              key={c.key}
              type="button"
              onClick={() => setActive(c.key)}
              className={cn(
                "flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                active === c.key
                  ? "border-ring bg-muted/50"
                  : "border-border hover:bg-muted/40",
              )}
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="text-xs text-muted-foreground">{c.order}</span>
                <span className="truncate">{c.title}</span>
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {c.risk === "high" && <Badge variant="warning">SME</Badge>}
                <Badge variant={(r?.mode ?? c.default_execution) === "council" ? "default" : "secondary"}>
                  {r?.mode ?? c.default_execution}
                </Badge>
              </span>
            </button>
          );
        })}
      </div>

      {/* Stage editor */}
      <div className="flex flex-col gap-4 rounded-lg border border-border p-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">
              {spec.order}. {spec.title}
            </span>
            {spec.risk === "high" && <Badge variant="warning">High risk · SME review</Badge>}
            {res?.uses_defaults && <Badge variant="outline">uses defaults</Badge>}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{spec.description}</p>
        </div>

        {/* Mode */}
        <div className="flex flex-col gap-1.5">
          <Label>Execution mode</Label>
          <div className="flex gap-2">
            {(["single", "council"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => update({ mode: m })}
                className={cn(
                  "flex-1 rounded-lg border px-3 py-2 text-sm transition-colors",
                  mode === m
                    ? "border-ring bg-muted/50 font-medium"
                    : "border-border hover:bg-muted/40",
                )}
              >
                {m === "single" ? "Single — one model" : "Council — deliberate + chairman"}
              </button>
            ))}
          </div>
        </div>

        {mode === "single" ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${active}-single`}>Model</Label>
            <ModelSelect
              id={`${active}-single`}
              value={cfg.single_model}
              options={models}
              onChange={(v) => update({ single_model: v })}
            />
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <Label>Council members</Label>
              <ModelMultiSelect
                values={cfg.council_models ?? []}
                options={models}
                onChange={(v) => update({ council_models: v })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${active}-chairman`}>Chairman model</Label>
              <ModelSelect
                id={`${active}-chairman`}
                value={cfg.chairman_model}
                options={models}
                onChange={(v) => update({ chairman_model: v })}
              />
            </div>
          </>
        )}

        {/* Prompts */}
        <div className="flex items-center justify-between">
          <Label>Prompts</Label>
          <Button size="xs" variant="ghost" onClick={() => onResetPrompts(active)}>
            <RotateCcw /> Reset to recommended
          </Button>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${active}-member-prompt`} className="text-xs text-muted-foreground">
            Member system prompt
          </Label>
          <Textarea
            id={`${active}-member-prompt`}
            rows={5}
            value={cfg.member_system_prompt ?? ""}
            placeholder={rec?.member_system_prompt ?? "Recommended prompt used when blank."}
            onChange={(e) => update({ member_system_prompt: e.target.value })}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label
            htmlFor={`${active}-chairman-prompt`}
            className="text-xs text-muted-foreground"
          >
            Chairman system prompt (council)
          </Label>
          <Textarea
            id={`${active}-chairman-prompt`}
            rows={5}
            value={cfg.chairman_system_prompt ?? ""}
            placeholder={rec?.chairman_system_prompt ?? "Recommended prompt used when blank."}
            onChange={(e) => update({ chairman_system_prompt: e.target.value })}
          />
        </div>

        {/* Resolved preview */}
        {res && (
          <div className="rounded-lg bg-muted/40 p-3 text-xs text-muted-foreground">
            <p className="mb-1 font-medium text-foreground">What a run will use</p>
            <p>Mode: {res.mode}</p>
            {res.mode === "single" ? (
              <p>Model: {res.single_model}</p>
            ) : (
              <p>
                Members: {res.council_models.join(", ") || "—"} · Chairman:{" "}
                {res.chairman_model}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
