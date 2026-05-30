"use client";

import { useEffect, useState } from "react";

import { GradePanel } from "@/components/projects/grade-panel";
import { SubmissionStatusBadge } from "@/components/projects/submission-status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import {
  getSubmissionDetail,
  listGradingQueue,
  type SubmissionDetail,
  type SubmissionListItem,
} from "@/lib/projects";

/**
 * Teacher grading workspace: the object-scoped submission queue (own classes
 * only) on the left, the selected submission's grading form on the right.
 *
 * Data is fetched inside effects (async IIFE + active guard); a `reloadKey`
 * counter triggers re-fetches after a grade is saved.
 */
export function GradingView() {
  const [queue, setQueue] = useState<SubmissionListItem[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const page = await listGradingQueue({ limit: 100 });
        if (active) setQueue(page.items);
      } catch (err) {
        if (active) {
          setError(err instanceof ApiError ? err.message : "Failed to load submissions.");
          setQueue([]);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    (async () => {
      try {
        const d = await getSubmissionDetail(selectedId);
        if (active) setDetail(d);
      } catch (err) {
        if (active) {
          setError(err instanceof ApiError ? err.message : "Failed to load the submission.");
          setDetail(null);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [selectedId, reloadKey]);

  const detailLoading = !!selectedId && detail?.submission.id !== selectedId;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Grading</h1>
        <p className="text-sm text-muted-foreground">
          Review and grade project submissions from your own classes.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Submissions</CardTitle>
            <CardDescription>
              {queue === null
                ? "Loading…"
                : `${queue.length} submission${queue.length === 1 ? "" : "s"} in your classes`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {queue === null ? (
              <Skeleton className="h-48 w-full" />
            ) : queue.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                No submissions yet for your classes.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Learner</TableHead>
                    <TableHead>Project</TableHead>
                    <TableHead>Class</TableHead>
                    <TableHead>Attempt</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {queue.map((s) => (
                    <TableRow
                      key={s.id}
                      onClick={() => setSelectedId(s.id)}
                      className={
                        "cursor-pointer " + (s.id === selectedId ? "bg-muted/60" : "")
                      }
                    >
                      <TableCell className="font-medium">{s.learner_name}</TableCell>
                      <TableCell className="text-muted-foreground">{s.project_title}</TableCell>
                      <TableCell className="text-muted-foreground">{s.class_name}</TableCell>
                      <TableCell className="text-muted-foreground">#{s.attempt_no}</TableCell>
                      <TableCell>
                        {s.graded ? (
                          <Badge variant="success">
                            {s.score != null ? `Graded · ${s.score}` : "Graded"}
                          </Badge>
                        ) : (
                          <SubmissionStatusBadge status={s.status} />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <div>
          {detailLoading && !detail ? (
            <Skeleton className="h-96 w-full" />
          ) : detail ? (
            <GradePanel
              key={detail.submission.id}
              detail={detail}
              onGraded={() => setReloadKey((k) => k + 1)}
            />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Select a submission</CardTitle>
                <CardDescription>
                  Choose a submission from the list to grade it against the rubric.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
