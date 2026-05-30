"use client";

import { Layers } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Modal } from "@/components/admin/modal";
import { StageCard } from "@/components/stages/stage-card";
import { StageRunDetail } from "@/components/stages/stage-run-detail";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type Course, listCourses } from "@/lib/courses";
import {
  type RunStageRequest,
  type StageRun,
  type StageStatus,
  getCourseStages,
  getStageRun,
  runStage,
} from "@/lib/stages";
import { cn } from "@/lib/utils";

export function StageBoard() {
  const { hasPermission } = useAuth();
  const canRun = hasPermission("stage.run");

  const [courses, setCourses] = useState<Course[]>([]);
  const [courseId, setCourseId] = useState<string>("");
  const [stages, setStages] = useState<StageStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingStages, setLoadingStages] = useState(false);
  const [runningKey, setRunningKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<StageRun | null>(null);

  useEffect(() => {
    if (!canRun) return;
    let active = true;
    (async () => {
      try {
        const page = await listCourses(100, 0);
        if (!active) return;
        setCourses(page.items);
        if (page.items.length > 0) setCourseId(page.items[0].id);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load courses.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [canRun]);

  // Manual refresh (event handlers) — shows the stage spinner.
  const loadStages = useCallback(async (id: string) => {
    setLoadingStages(true);
    try {
      const data = await getCourseStages(id);
      setStages(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load stages.");
    } finally {
      setLoadingStages(false);
    }
  }, []);

  // Reload when the selected course changes. State is only set after the await
  // (or in finally), so this never sets state synchronously inside the effect.
  useEffect(() => {
    if (!courseId) return;
    let active = true;
    (async () => {
      try {
        const data = await getCourseStages(courseId);
        if (active) {
          setStages(data);
          setError(null);
        }
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load stages.");
      } finally {
        if (active) setLoadingStages(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [courseId]);

  const onRun = useCallback(
    async (stageKey: string, req: RunStageRequest) => {
      if (!courseId) return;
      setRunningKey(stageKey);
      setError(null);
      try {
        const run = await runStage(courseId, stageKey, req);
        setActiveRun(run);
        await loadStages(courseId);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Stage run failed.");
      } finally {
        setRunningKey(null);
      }
    },
    [courseId, loadStages],
  );

  const onView = useCallback(async (runId: string) => {
    try {
      const run = await getStageRun(runId);
      setActiveRun(run);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load run.");
    }
  }, []);

  const onReviewed = useCallback(
    (run: StageRun) => {
      setActiveRun(run);
      if (courseId) loadStages(courseId);
    },
    [courseId, loadStages],
  );

  if (!canRun) {
    return (
      <div className="mx-auto w-full max-w-3xl py-10">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Maestro Studio</CardTitle>
            <CardDescription>
              You don&apos;t have permission to run stage features.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 py-8">
      <header className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Layers className="size-5" />
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-semibold tracking-tight">Maestro Studio</h1>
          <p className="text-sm text-muted-foreground">
            The 12 stages as independent features. Run or re-run any stage, in single or
            council mode — order is up to you.
          </p>
        </div>
      </header>

      <div className="flex items-center gap-2">
        <label htmlFor="course" className="text-sm text-muted-foreground">
          Course
        </label>
        <select
          id="course"
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
          disabled={loading}
          className={cn(
            "h-9 min-w-64 rounded-lg border border-border bg-background px-3 text-sm shadow-sm",
            "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
          )}
        >
          {courses.length === 0 && <option value="">No courses — create one first</option>}
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {loading || loadingStages ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {stages.map((s) => (
            <StageCard
              key={s.key}
              stage={s}
              running={runningKey === s.key}
              onRun={onRun}
              onView={onView}
            />
          ))}
        </div>
      )}

      <Modal
        open={activeRun !== null}
        onClose={() => setActiveRun(null)}
        title={
          activeRun
            ? stages.find((s) => s.key === activeRun.stage_key)?.title ?? "Stage run"
            : "Stage run"
        }
        description="Run output, council transcript, and SME governance."
        className="max-w-3xl"
      >
        {activeRun && <StageRunDetail run={activeRun} onReviewed={onReviewed} />}
      </Modal>
    </div>
  );
}
