"use client";

import { Eye, Loader2, Play, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { RunStageRequest, StageStatus } from "@/lib/stages";
import { cn } from "@/lib/utils";

function reviewVariant(status: string) {
  if (status === "approved") return "success" as const;
  if (status === "rejected") return "destructive" as const;
  if (status === "needs_review") return "warning" as const;
  return "secondary" as const;
}

export function StageCard({
  stage,
  running,
  onRun,
  onView,
}: {
  stage: StageStatus;
  running: boolean;
  onRun: (stageKey: string, req: RunStageRequest) => void;
  onView: (runId: string) => void;
}) {
  const [mode, setMode] = useState<"single" | "council">(
    (stage.default_execution as "single" | "council") ?? "single",
  );
  const [syllabus, setSyllabus] = useState("");
  const last = stage.last_run;

  const run = () => {
    const options = stage.key === "intake" && syllabus.trim() ? { syllabus_text: syllabus.trim() } : {};
    onRun(stage.key, { mode, options });
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{stage.order}</span>
            <span className="truncate text-sm font-semibold">{stage.title}</span>
          </div>
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
            {stage.description}
          </p>
        </div>
        {stage.risk === "high" && <Badge variant="warning">SME</Badge>}
      </div>

      {last ? (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <Badge
            variant={
              last.status === "succeeded"
                ? "success"
                : last.status === "failed"
                  ? "destructive"
                  : "secondary"
            }
          >
            {last.status}
          </Badge>
          <Badge variant={last.execution_mode === "council" ? "default" : "secondary"}>
            {last.execution_mode}
          </Badge>
          <Badge variant={reviewVariant(last.review_status)}>{last.review_status}</Badge>
          {last.stubbed && <Badge variant="outline">stub</Badge>}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">Not run yet.</p>
      )}

      {stage.key === "intake" && (
        <Textarea
          rows={3}
          value={syllabus}
          placeholder="Paste syllabus text (optional)…"
          onChange={(e) => setSyllabus(e.target.value)}
          className="text-xs"
        />
      )}

      <div className="mt-auto flex items-center gap-2">
        <div className="flex overflow-hidden rounded-lg border border-border text-xs">
          {(["single", "council"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={cn(
                "px-2.5 py-1 transition-colors",
                mode === m ? "bg-muted font-medium" : "hover:bg-muted/40",
              )}
            >
              {m}
            </button>
          ))}
        </div>
        <Button size="sm" onClick={run} disabled={running}>
          {running ? (
            <Loader2 className="animate-spin" />
          ) : last ? (
            <RefreshCw />
          ) : (
            <Play />
          )}
          {running ? "Running…" : last ? "Re-run" : "Run"}
        </Button>
        {last && (
          <Button size="sm" variant="ghost" onClick={() => onView(last.id)}>
            <Eye /> View
          </Button>
        )}
      </div>
    </div>
  );
}
