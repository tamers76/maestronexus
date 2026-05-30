"use client";

import { Check, ShieldAlert, X } from "lucide-react";
import { useState } from "react";

import { CouncilTranscriptView } from "@/components/stages/council-transcript";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type StageRun, approveStageRun, rejectStageRun } from "@/lib/stages";

function reviewVariant(status: string) {
  if (status === "approved") return "success" as const;
  if (status === "rejected") return "destructive" as const;
  if (status === "needs_review") return "warning" as const;
  return "secondary" as const;
}

export function StageRunDetail({
  run,
  onReviewed,
}: {
  run: StageRun;
  onReviewed: (run: StageRun) => void;
}) {
  const { hasPermission } = useAuth();
  const canReview = hasPermission("stage.review");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gaps = (run.output?.gaps ?? []) as unknown[];
  const finalText = run.output?.text ?? "";
  const isCouncil = run.execution_mode === "council";
  const needsReview = run.review_status === "needs_review";

  const doReview = async (approve: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const updated = approve
        ? await approveStageRun(run.id)
        : await rejectStageRun(run.id);
      onReviewed(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Review failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={run.status === "succeeded" ? "success" : run.status === "failed" ? "destructive" : "secondary"}>
          {run.status}
        </Badge>
        <Badge variant={isCouncil ? "default" : "secondary"}>{run.execution_mode}</Badge>
        <Badge variant={reviewVariant(run.review_status)}>{run.review_status}</Badge>
        <Badge variant="outline">risk {run.risk_score.toFixed(2)}</Badge>
        {run.output?.stubbed && <Badge variant="outline">offline stub</Badge>}
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {gaps.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
          <p className="mb-1 flex items-center gap-1 font-medium text-amber-600 dark:text-amber-400">
            <ShieldAlert className="size-4" /> Gaps to confirm
          </p>
          <ul className="list-inside list-disc text-xs text-muted-foreground">
            {gaps.map((g, i) => (
              <li key={i}>{typeof g === "string" ? g : JSON.stringify(g)}</li>
            ))}
          </ul>
        </div>
      )}

      {isCouncil ? (
        <CouncilTranscriptView transcript={run.council_transcript} finalText={finalText} />
      ) : (
        <div className="rounded-lg border border-border p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Output</p>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs">
            {run.output?.error ? `Error: ${run.output.error}` : finalText}
          </pre>
        </div>
      )}

      {canReview && needsReview && (
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => doReview(true)} disabled={busy}>
            <Check /> Approve
          </Button>
          <Button size="sm" variant="destructive" onClick={() => doReview(false)} disabled={busy}>
            <X /> Reject
          </Button>
          <span className="text-xs text-muted-foreground">SME governance (docx §10)</span>
        </div>
      )}
    </div>
  );
}
