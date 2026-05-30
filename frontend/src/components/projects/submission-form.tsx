"use client";

import { useEffect, useState } from "react";

import { SubmissionStatusBadge } from "@/components/projects/submission-status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import {
  getProject,
  listMySubmissions,
  type Project,
  submitProject,
  type Submission,
} from "@/lib/projects";

/**
 * Reusable per-learner submission widget (docs/08). Drop it into the learner
 * journey for a given project node; it loads the project, shows the learner's
 * own attempt history, and lets them submit a new attempt. Loosely coupled — it
 * only needs a `projectId`.
 */
export function SubmissionForm({
  projectId,
  onSubmitted,
}: {
  projectId: string;
  onSubmitted?: (submission: Submission) => void;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [history, setHistory] = useState<Submission[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [proj, subs] = await Promise.all([
          getProject(projectId),
          listMySubmissions(projectId),
        ]);
        if (active) {
          setProject(proj);
          setHistory(subs);
          setLoaded(true);
        }
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load the project.");
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId, reloadKey]);

  const atLimit =
    !!project && project.max_submissions > 0 && history.length >= project.max_submissions;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const submission = await submitProject(projectId, { text });
      setText("");
      setReloadKey((k) => k + 1);
      onSubmitted?.(submission);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit your work.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!loaded) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Loading project…</CardTitle>
        </CardHeader>
      </Card>
    );
  }

  const instructionsText =
    project && typeof project.instructions?.text === "string"
      ? (project.instructions.text as string)
      : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{project?.title ?? "Project"}</CardTitle>
        <CardDescription>
          {instructionsText ?? "Submit your work for this project."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {history.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <Label>Your submissions</Label>
            <div className="flex flex-col gap-1.5">
              {history.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <span>Attempt #{s.attempt_no}</span>
                  <SubmissionStatusBadge status={s.status} />
                </div>
              ))}
            </div>
          </div>
        )}

        {atLimit ? (
          <p className="text-sm text-muted-foreground">
            You have reached the submission limit for this project.
          </p>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="submission-text">Your work</Label>
              <Textarea
                id="submission-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Describe your work, paste a link, or write your response…"
                required
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Submitting…" : "Submit"}
              </Button>
            </div>
          </form>
        )}
        {error && atLimit && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}
