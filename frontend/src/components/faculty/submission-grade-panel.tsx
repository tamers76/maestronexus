"use client";

import { Gavel, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Evaluation,
  type EvaluationRecommendation,
  type Submission,
  SUBMISSION_STATUS_META,
  evaluateSubmission,
  finalizeGrade,
  getEvaluation,
  requestRevision,
} from "@/lib/blueprint";

const RECOMMENDATIONS: EvaluationRecommendation[] = [
  "accept",
  "minor_revision",
  "major_revision",
  "missing_process_evidence",
  "ai_use_clarification",
  "defense_requested",
  "sme_review",
  "not_recommended",
];

function field(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/**
 * Faculty grading surface for a single submission: review the package, record a
 * rubric-based evaluation recommendation, request a revision, or finalize the
 * academic grade. Gated by `project.grade`.
 */
export function SubmissionGradePanel({
  submission,
  onChanged,
}: {
  submission: Submission;
  onChanged?: (submission: Submission) => void;
}) {
  const { hasPermission } = useAuth();
  const canGrade = hasPermission("project.grade");

  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [recommendation, setRecommendation] = useState<EvaluationRecommendation>("accept");
  const [feedbackLearner, setFeedbackLearner] = useState("");
  const [feedbackSme, setFeedbackSme] = useState("");
  const [integrityFlag, setIntegrityFlag] = useState(false);
  const [grade, setGrade] = useState("");
  const [publication, setPublication] = useState("");
  const [revisionKind, setRevisionKind] = useState<"minor" | "major">("minor");
  const [revisionNote, setRevisionNote] = useState("");

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      const ev = await getEvaluation(submission.id).catch(() => null);
      if (!active || !ev) return;
      setEvaluation(ev);
      if (ev.recommendation) setRecommendation(ev.recommendation as EvaluationRecommendation);
      if (ev.feedback_learner) setFeedbackLearner(ev.feedback_learner);
      if (ev.feedback_sme) setFeedbackSme(ev.feedback_sme);
      setIntegrityFlag(ev.integrity_flag);
      if (typeof ev.grade === "number") setGrade(String(ev.grade));
      if (ev.publication_potential) setPublication(ev.publication_potential);
    })();
    return () => {
      active = false;
    };
  }, [submission.id]);

  const wrap = useCallback(async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }, []);

  const onEvaluate = () =>
    wrap("evaluate", async () => {
      const ev = await evaluateSubmission(submission.id, {
        recommendation,
        feedback_learner: feedbackLearner.trim() || null,
        feedback_sme: feedbackSme.trim() || null,
        integrity_flag: integrityFlag,
        grade: grade ? Number(grade) : null,
        publication_potential: publication.trim() || null,
        evaluator_kind: "sme",
      });
      setEvaluation(ev);
    });

  const onFinalize = () =>
    wrap("finalize", async () => {
      if (!grade) {
        setError("Enter a grade to finalize.");
        return;
      }
      const ev = await finalizeGrade(submission.id, {
        grade: Number(grade),
        feedback_learner: feedbackLearner.trim() || null,
        publication_potential: publication.trim() || null,
      });
      setEvaluation(ev);
      onChanged?.({ ...submission, status: "graded" });
    });

  const onRequestRevision = () =>
    wrap("revision", async () => {
      const updated = await requestRevision(submission.id, {
        kind: revisionKind,
        note: revisionNote.trim() || null,
      });
      onChanged?.(updated);
    });

  const statusMeta = SUBMISSION_STATUS_META[submission.status];

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={statusMeta?.variant ?? "outline"}>
          {statusMeta?.label ?? submission.status}
        </Badge>
        <span className="text-xs text-muted-foreground">v{submission.version}</span>
        {evaluation?.finalized && typeof evaluation.grade === "number" && (
          <Badge variant="success">Final grade: {evaluation.grade}</Badge>
        )}
      </div>

      {/* Submission package */}
      <div className="rounded-lg border border-border bg-muted/20 p-2.5 text-xs">
        <p className="mb-1 font-medium text-muted-foreground">Submission</p>
        <p className="whitespace-pre-wrap leading-snug">
          {field(submission.package?.response) || "No written response."}
        </p>
        {field(submission.package?.ai_use_disclosure) && (
          <p className="mt-2 text-muted-foreground">
            <span className="font-medium">AI-use disclosure:</span>{" "}
            {field(submission.package.ai_use_disclosure)}
          </p>
        )}
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {!canGrade ? (
        <p className="text-xs text-muted-foreground">
          You don&apos;t have permission to grade submissions.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Recommendation</Label>
              <select
                value={recommendation}
                onChange={(e) =>
                  setRecommendation(e.target.value as EvaluationRecommendation)
                }
                className="h-8 rounded-lg border border-border bg-background px-2 text-xs"
              >
                {RECOMMENDATIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Grade</Label>
              <Input
                type="number"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
                placeholder="0–100"
                className="h-8 text-xs"
              />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Feedback to learner</Label>
            <Textarea
              rows={2}
              value={feedbackLearner}
              onChange={(e) => setFeedbackLearner(e.target.value)}
              className="text-xs"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">SME / internal notes</Label>
            <Textarea
              rows={2}
              value={feedbackSme}
              onChange={(e) => setFeedbackSme(e.target.value)}
              className="text-xs"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={integrityFlag}
                onChange={(e) => setIntegrityFlag(e.target.checked)}
              />
              Integrity flag
            </label>
            <label className="flex items-center gap-1.5">
              <span>Publication potential</span>
              <Input
                value={publication}
                onChange={(e) => setPublication(e.target.value)}
                placeholder="none / internal / public"
                className="h-7 w-40 text-xs"
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={onEvaluate} disabled={busy === "evaluate"}>
              {busy === "evaluate" ? <Loader2 className="animate-spin" /> : <Sparkles />}
              Record evaluation
            </Button>
            <Button size="sm" onClick={onFinalize} disabled={busy === "finalize"}>
              {busy === "finalize" ? <Loader2 className="animate-spin" /> : <Gavel />}
              Finalize grade
            </Button>
          </div>

          {/* Request revision */}
          <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Revision</Label>
              <select
                value={revisionKind}
                onChange={(e) => setRevisionKind(e.target.value as "minor" | "major")}
                className="h-8 rounded-lg border border-border bg-background px-2 text-xs"
              >
                <option value="minor">Minor</option>
                <option value="major">Major</option>
              </select>
            </div>
            <Input
              value={revisionNote}
              onChange={(e) => setRevisionNote(e.target.value)}
              placeholder="Revision note…"
              className="h-8 flex-1 text-xs"
            />
            <Button
              size="sm"
              variant="outline"
              onClick={onRequestRevision}
              disabled={busy === "revision"}
            >
              {busy === "revision" ? <Loader2 className="animate-spin" /> : <RotateCcw />}
              Request revision
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
