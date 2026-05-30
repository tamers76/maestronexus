"use client";

import { Inbox } from "lucide-react";
import { useEffect, useState } from "react";

import { EnrollmentSubmissions } from "@/components/faculty/enrollment-submissions";
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
  type ClassOut,
  type EnrollmentOut,
  listClasses,
  listEnrollments,
} from "@/lib/enrollment";
import { cn } from "@/lib/utils";

/**
 * Faculty assessment submissions queue: pick a class, pick a learner, then
 * evaluate / grade / request revisions and manage Mastery Credits. Gated by
 * `project.grade`.
 */
export function SubmissionsQueue() {
  const { user, hasPermission } = useAuth();
  const canGrade = hasPermission("project.grade");

  const [classes, setClasses] = useState<ClassOut[] | null>(null);
  const [classId, setClassId] = useState<string>("");
  const [enrollments, setEnrollments] = useState<EnrollmentOut[] | null>(null);
  const [enrollmentId, setEnrollmentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canGrade) return;
    let active = true;
    (async () => {
      try {
        const page = await listClasses(user?.id);
        if (!active) return;
        setClasses(page.items);
        if (page.items.length > 0) setClassId(page.items[0].id);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load classes.");
      }
    })();
    return () => {
      active = false;
    };
  }, [canGrade, user?.id]);

  useEffect(() => {
    if (!classId) return;
    let active = true;
    (async () => {
      try {
        const page = await listEnrollments({ class_id: classId });
        if (!active) return;
        setEnrollments(page.items);
        setEnrollmentId(null);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load enrollments.");
      }
    })();
    return () => {
      active = false;
    };
  }, [classId]);

  if (!canGrade) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Submissions</CardTitle>
          <CardDescription>
            You don&apos;t have permission to grade submissions.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Inbox className="size-5" />
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Submissions</h1>
          <p className="text-sm text-muted-foreground">
            Evaluate contribution assessments, finalize grades, and award Mastery
            Credits.
          </p>
        </div>
      </header>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex items-center gap-2">
        <label htmlFor="queue-class" className="text-sm text-muted-foreground">
          Class
        </label>
        <select
          id="queue-class"
          value={classId}
          onChange={(e) => setClassId(e.target.value)}
          className="h-9 min-w-64 rounded-lg border border-border bg-background px-3 text-sm"
        >
          {classes === null && <option value="">Loading…</option>}
          {classes?.length === 0 && <option value="">No classes</option>}
          {classes?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Learners</CardTitle>
          <CardDescription>Select a learner to review their submissions.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {enrollments === null ? (
            <Skeleton className="h-9 w-full" />
          ) : enrollments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No learners enrolled.</p>
          ) : (
            enrollments.map((e) => (
              <Button
                key={e.id}
                size="sm"
                variant={e.id === enrollmentId ? "default" : "outline"}
                onClick={() => setEnrollmentId(e.id)}
                className={cn(e.id === enrollmentId && "ring-1 ring-primary/30")}
              >
                {e.user_id.slice(0, 8)} · {e.status}
              </Button>
            ))
          )}
        </CardContent>
      </Card>

      {enrollmentId && <EnrollmentSubmissions key={enrollmentId} enrollmentId={enrollmentId} />}
    </div>
  );
}
