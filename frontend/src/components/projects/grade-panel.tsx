"use client";

import { useMemo, useState } from "react";

import { SubmissionStatusBadge } from "@/components/projects/submission-status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import {
  gradeSubmission,
  type RubricCriterion,
  type SubmissionDetail,
} from "@/lib/projects";

/**
 * Grading form for a single submission: shows the learner's payload, the rubric
 * criteria (if any), and lets the teacher enter rubric scores, an overall score,
 * and feedback. Calls back when a grade is saved so the queue can refresh.
 *
 * The parent remounts this with `key={submission.id}`, so form state is
 * initialised directly from props — no hydrating effect needed.
 */
export function GradePanel({
  detail,
  onGraded,
}: {
  detail: SubmissionDetail;
  onGraded: () => void;
}) {
  const criteria = useMemo<RubricCriterion[]>(
    () => detail.rubric?.criteria?.items ?? [],
    [detail.rubric],
  );

  const [rubricScores, setRubricScores] = useState<Record<string, string>>(() => {
    const next: Record<string, string> = {};
    for (const [k, v] of Object.entries(detail.grade?.rubric_scores ?? {})) {
      next[k] = String(v);
    }
    return next;
  });
  const [score, setScore] = useState<string>(
    detail.grade?.score != null ? String(detail.grade.score) : "",
  );
  const [feedback, setFeedback] = useState<string>(detail.feedback?.body ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function onSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const parsedRubric: Record<string, number> = {};
      for (const [k, v] of Object.entries(rubricScores)) {
        if (v !== "") parsedRubric[k] = Number(v);
      }
      await gradeSubmission(detail.submission.id, {
        score: score === "" ? null : Number(score),
        rubric_scores: parsedRubric,
        feedback,
      });
      setSaved(true);
      onGraded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the grade.");
    } finally {
      setSaving(false);
    }
  }

  const payloadEntries = Object.entries(detail.submission.payload ?? {});

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">{detail.project.title}</CardTitle>
          <SubmissionStatusBadge status={detail.submission.status} />
        </div>
        <p className="text-sm text-muted-foreground">
          {detail.learner_name} · {detail.class_name} · attempt {detail.submission.attempt_no}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {/* Submission payload */}
        <div className="flex flex-col gap-1.5">
          <Label>Submission</Label>
          {payloadEntries.length === 0 ? (
            <p className="text-sm text-muted-foreground">No content provided.</p>
          ) : (
            <dl className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
              {payloadEntries.map(([k, v]) => (
                <div key={k} className="flex flex-col gap-0.5 py-1">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {k}
                  </dt>
                  <dd className="whitespace-pre-wrap break-words">
                    {typeof v === "string" ? v : JSON.stringify(v)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>

        {/* Rubric */}
        {criteria.length > 0 && (
          <div className="flex flex-col gap-2">
            <Label>Rubric</Label>
            <div className="flex flex-col gap-2">
              {criteria.map((c) => (
                <div key={c.key} className="flex items-center justify-between gap-3">
                  <span className="text-sm">
                    {c.label}
                    {c.max != null && (
                      <span className="text-muted-foreground"> / {c.max}</span>
                    )}
                  </span>
                  <Input
                    type="number"
                    className="w-24"
                    value={rubricScores[c.key] ?? ""}
                    min={0}
                    max={c.max}
                    onChange={(e) =>
                      setRubricScores((prev) => ({ ...prev, [c.key]: e.target.value }))
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overall score */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="overall-score">Overall score</Label>
          <Input
            id="overall-score"
            type="number"
            className="w-32"
            value={score}
            onChange={(e) => setScore(e.target.value)}
            placeholder="0–100"
          />
        </div>

        {/* Feedback */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="feedback">Feedback</Label>
          <Textarea
            id="feedback"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Share what went well and what to improve…"
          />
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex items-center gap-3">
          <Button onClick={onSave} disabled={saving}>
            {saving ? "Saving…" : "Save grade"}
          </Button>
          {saved && <span className="text-sm text-emerald-600">Saved</span>}
        </div>
      </CardContent>
    </Card>
  );
}
