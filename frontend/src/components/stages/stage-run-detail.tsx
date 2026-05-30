"use client";

import { Check, FileText, ListTree, ShieldAlert, X } from "lucide-react";
import { useState } from "react";

import { CouncilTranscriptView } from "@/components/stages/council-transcript";
import {
  ApprovalImpact,
  StageArtifactView,
} from "@/components/stages/stage-artifact-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type StageRun,
  type StageStatus,
  approveStageRun,
  rejectStageRun,
} from "@/lib/stages";
import { cn } from "@/lib/utils";

function reviewVariant(status: string) {
  if (status === "approved") return "success" as const;
  if (status === "rejected") return "destructive" as const;
  if (status === "needs_review") return "warning" as const;
  return "secondary" as const;
}

type Tab = "artifact" | "raw";

export function StageRunDetail({
  run,
  stage,
  onReviewed,
}: {
  run: StageRun;
  stage?: StageStatus | null;
  onReviewed: (run: StageRun) => void;
}) {
  const { hasPermission } = useAuth();
  const canReview = hasPermission("stage.review");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gaps = (run.output?.gaps ?? []) as unknown[];
  const finalText = run.output?.text ?? "";
  const artifact = run.output?.artifact ?? null;
  const outputKind = run.output?.output_kind;
  const isCouncil = run.execution_mode === "council";
  const needsReview = run.review_status === "needs_review";
  const promotesTo = stage?.promotes_to ?? null;
  const hasArtifact = artifact !== null && artifact !== undefined;

  const [tab, setTab] = useState<Tab>(hasArtifact ? "artifact" : "raw");

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
        <Badge
          variant={
            run.status === "succeeded"
              ? "success"
              : run.status === "failed"
                ? "destructive"
                : "secondary"
          }
        >
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

      {/* Structured artifact / raw output tabs */}
      <div className="flex overflow-hidden rounded-lg border border-border text-xs">
        {(["artifact", "raw"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 transition-colors",
              tab === t ? "bg-muted font-medium" : "hover:bg-muted/40",
            )}
          >
            {t === "artifact" ? (
              <ListTree className="size-3.5" />
            ) : (
              <FileText className="size-3.5" />
            )}
            {t === "artifact" ? "Structured artifact" : "Narrative / council"}
          </button>
        ))}
      </div>

      {tab === "artifact" ? (
        <StageArtifactView artifact={artifact} outputKind={outputKind} />
      ) : isCouncil ? (
        <CouncilTranscriptView transcript={run.council_transcript} finalText={finalText} />
      ) : (
        <div className="rounded-lg border border-border p-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Output</p>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs">
            {run.output?.error ? `Error: ${run.output.error}` : finalText}
          </pre>
        </div>
      )}

      {/* Approval impact preview — what promotion will write into the course */}
      {needsReview && <ApprovalImpact promotesTo={promotesTo} artifact={artifact} />}

      {canReview && needsReview && (
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => doReview(true)} disabled={busy}>
            <Check /> Approve &amp; promote
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => doReview(false)}
            disabled={busy}
          >
            <X /> Reject
          </Button>
          <span className="text-xs text-muted-foreground">SME governance (docx §10)</span>
        </div>
      )}
    </div>
  );
}
