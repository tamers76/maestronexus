"use client";

import { CheckCircle2, ListChecks, Loader2, Sparkles, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
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
  type CourseClos,
  type LearningOutcome,
  getCourseClos,
} from "@/lib/courses";
import {
  type StageRun,
  approveStageRun,
  getStageRun,
  listStageRuns,
  rejectStageRun,
  runStage,
} from "@/lib/stages";

type RefinedClo = {
  code?: string;
  original_statement?: string;
  statement?: string;
  bloom_level?: string;
  knowledge_type?: string;
  action_verb?: string;
  measurable?: boolean;
  capability_statement?: string;
  evidence_of_mastery?: string;
  adaptive_readiness?: string;
  rationale?: string;
};

function attrBadges(attributes: Record<string, unknown>) {
  const out: { label: string; key: string }[] = [];
  const bloom = attributes["bloom_level"];
  if (typeof bloom === "string" && bloom) out.push({ key: "bloom", label: bloom });
  const knowledge = attributes["knowledge_type"];
  if (typeof knowledge === "string" && knowledge)
    out.push({ key: "knowledge", label: knowledge });
  if (attributes["measurable"] === true) out.push({ key: "measurable", label: "measurable" });
  if (attributes["refined"] === true) out.push({ key: "refined", label: "refined" });
  return out;
}

function refinedClosFrom(run: StageRun | null): RefinedClo[] {
  if (!run || run.status !== "succeeded") return [];
  const artifact = run.output?.artifact as { clos?: RefinedClo[] } | undefined;
  if (!artifact || !Array.isArray(artifact.clos)) return [];
  return artifact.clos;
}

export function ClosPanel({ courseId }: { courseId: string }) {
  const { hasPermission } = useAuth();
  const canRun = hasPermission("stage.run");
  const canReview = hasPermission("stage.review");

  const [data, setData] = useState<CourseClos | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [refinementRun, setRefinementRun] = useState<StageRun | null>(null);
  const [refining, setRefining] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const clos = await getCourseClos(courseId);
      setData(clos);
      if (clos.clo_refinement_run) {
        const run = await getStageRun(clos.clo_refinement_run.id);
        setRefinementRun(run);
      } else {
        setRefinementRun(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load CLOs.");
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const clos = await getCourseClos(courseId);
        let run: StageRun | null = null;
        if (clos.clo_refinement_run) {
          run = await getStageRun(clos.clo_refinement_run.id);
        }
        if (!active) return;
        setData(clos);
        setRefinementRun(run);
        setError(null);
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Failed to load CLOs.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [courseId]);

  const onRefine = useCallback(async () => {
    setRefining(true);
    setError(null);
    try {
      const run = await runStage(courseId, "clo_refinement");
      setRefinementRun(run);
      // Refresh the latest-run pointer.
      const runs = await listStageRuns(courseId, "clo_refinement");
      if (runs[0]) setRefinementRun(runs[0]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not refine CLOs.");
    } finally {
      setRefining(false);
    }
  }, [courseId]);

  const onReview = useCallback(
    async (approve: boolean) => {
      if (!refinementRun) return;
      setReviewing(true);
      setError(null);
      try {
        if (approve) await approveStageRun(refinementRun.id);
        else await rejectStageRun(refinementRun.id);
        await load();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not submit review.");
      } finally {
        setReviewing(false);
      }
    },
    [refinementRun, load],
  );

  const proposed = refinedClosFrom(refinementRun);
  const pendingApproval =
    refinementRun?.status === "succeeded" &&
    refinementRun.review_status !== "approved" &&
    refinementRun.review_status !== "rejected" &&
    proposed.length > 0;
  const clos = data?.clos ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <ListChecks className="size-4 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Course Learning Outcomes</CardTitle>
              <CardDescription>
                {loading
                  ? "Loading…"
                  : `${clos.length} CLO(s)` +
                    (data?.intake_run?.stubbed
                      ? " — intake ran with a stubbed model (configure an AI provider for real extraction)"
                      : "")}
              </CardDescription>
            </div>
          </div>
          {canRun && clos.length > 0 && (
            <Button size="sm" variant="outline" onClick={onRefine} disabled={refining}>
              {refining ? <Loader2 className="animate-spin" /> : <Sparkles />}
              {refining ? "Refining…" : "Refine CLOs"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error && (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {loading ? (
          <>
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </>
        ) : clos.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            No CLOs yet. Create this course from a syllabus or manual entry to extract
            outcomes.
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {clos.map((clo: LearningOutcome) => (
              <li
                key={clo.id}
                className="rounded-lg border border-border p-3 text-sm"
              >
                <div className="flex items-center gap-2">
                  {clo.code && (
                    <Badge variant="secondary" className="font-mono">
                      {clo.code}
                    </Badge>
                  )}
                  {attrBadges(clo.attributes).map((b) => (
                    <Badge key={b.key} variant="outline">
                      {b.label}
                    </Badge>
                  ))}
                </div>
                <p className="mt-1.5 leading-snug">{clo.statement}</p>
                {typeof clo.attributes["evidence_of_mastery"] === "string" && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Evidence of mastery: {String(clo.attributes["evidence_of_mastery"])}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}

        {pendingApproval && (
          <div className="flex flex-col gap-3 rounded-lg border border-ring/40 bg-muted/40 p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="size-4 text-primary" />
                Proposed refinements
                {refinementRun?.output?.stubbed && (
                  <Badge variant="outline">stubbed</Badge>
                )}
              </div>
              {canReview && (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => onReview(true)}
                    disabled={reviewing}
                  >
                    <CheckCircle2 /> Approve &amp; apply
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onReview(false)}
                    disabled={reviewing}
                  >
                    <XCircle /> Reject
                  </Button>
                </div>
              )}
            </div>
            <ul className="flex flex-col gap-2">
              {proposed.map((r, i) => (
                <li
                  key={r.code ?? i}
                  className="rounded-md border border-border bg-background p-3 text-sm"
                >
                  <div className="flex items-center gap-2">
                    {r.code && (
                      <Badge variant="secondary" className="font-mono">
                        {r.code}
                      </Badge>
                    )}
                    {r.bloom_level && <Badge variant="outline">{r.bloom_level}</Badge>}
                    {r.measurable && <Badge variant="outline">measurable</Badge>}
                  </div>
                  {r.original_statement && (
                    <p className="mt-1.5 text-xs text-muted-foreground line-through">
                      {r.original_statement}
                    </p>
                  )}
                  <p className="mt-1 leading-snug">{r.statement}</p>
                  {r.evidence_of_mastery && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Evidence of mastery: {r.evidence_of_mastery}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {!pendingApproval &&
          refinementRun?.review_status === "approved" &&
          !loading && (
            <p className="text-xs text-muted-foreground">
              Latest refinement approved and applied to the CLOs above.
            </p>
          )}
      </CardContent>
    </Card>
  );
}
