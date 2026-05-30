"use client";

import { BarChart3, BadgeCheck, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { StatCard } from "@/components/admin/stat-card";
import { StageArtifactView } from "@/components/stages/stage-artifact-view";
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
  type Contribution,
  type CourseAnalytics,
  type VerificationStatus,
  type VisibilityLevel,
  READINESS_META,
  VERIFICATION_META,
  getCourseAnalytics,
  listPublicationCandidates,
  verifyContribution,
} from "@/lib/blueprint";
import { type Course, listCourses } from "@/lib/courses";

function CountRow({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (entries.length === 0)
    return <p className="text-sm text-muted-foreground">No data.</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([k, v]) => (
        <Badge key={k} variant="outline">
          {k}: <span className="font-semibold">{v}</span>
        </Badge>
      ))}
    </div>
  );
}

/**
 * Faculty Blueprint analytics dashboard: readiness, submissions, evaluations,
 * publication candidates (with SME verification), Mastery Credits, and
 * continuous-improvement signals for one course. Gated by `report.view_class`.
 */
export function AnalyticsDashboard() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("report.view_class");
  const canVerify = hasPermission("stage.review");

  const [courses, setCourses] = useState<Course[] | null>(null);
  const [courseId, setCourseId] = useState<string>("");
  const [manualId, setManualId] = useState("");
  const [analytics, setAnalytics] = useState<CourseAnalytics | null>(null);
  const [candidates, setCandidates] = useState<Contribution[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!canView) return;
    let active = true;
    (async () => {
      try {
        const page = await listCourses(100, 0);
        if (!active) return;
        setCourses(page.items);
        if (page.items.length > 0) setCourseId(page.items[0].id);
      } catch {
        // Course manager listing may be forbidden for pure report viewers;
        // fall back to a manual course-id entry.
        if (active) setCourses([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [canView]);

  useEffect(() => {
    if (!courseId) return;
    let active = true;
    (async () => {
      try {
        const [a, c] = await Promise.all([
          getCourseAnalytics(courseId),
          listPublicationCandidates(courseId).catch(() => [] as Contribution[]),
        ]);
        if (!active) return;
        setAnalytics(a);
        setCandidates(c);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof ApiError ? err.message : "Failed to load analytics.");
        setAnalytics(null);
      }
    })();
    return () => {
      active = false;
    };
  }, [courseId]);

  const showSkeleton = !!courseId && analytics === null && !error;

  const onVerify =
    (id: string, status: VerificationStatus, visibility?: VisibilityLevel) =>
    () => {
      void (async () => {
        setBusy(id);
        setError(null);
        try {
          const updated = await verifyContribution(id, {
            verification_status: status,
            visibility_level: visibility,
          });
          setCandidates((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Verification failed.");
        } finally {
          setBusy(null);
        }
      })();
    };

  if (!canView) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Analytics</CardTitle>
          <CardDescription>
            You don&apos;t have permission to view class analytics.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <BarChart3 className="size-5" />
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Blueprint analytics</h1>
          <p className="text-sm text-muted-foreground">
            Readiness, submissions, grades, publication candidates, and Mastery
            Credits — with continuous-improvement signals.
          </p>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {courses && courses.length > 0 ? (
          <>
            <label htmlFor="an-course" className="text-sm text-muted-foreground">
              Course
            </label>
            <select
              id="an-course"
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              className="h-9 min-w-64 rounded-lg border border-border bg-background px-3 text-sm"
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setCourseId(manualId.trim());
            }}
            className="flex items-center gap-2"
          >
            <label htmlFor="an-course-id" className="text-sm text-muted-foreground">
              Course ID
            </label>
            <input
              id="an-course-id"
              value={manualId}
              onChange={(e) => setManualId(e.target.value)}
              placeholder="Paste a course ID"
              className="h-9 min-w-64 rounded-lg border border-border bg-background px-3 text-sm"
            />
            <Button type="submit" size="sm" variant="outline">
              Load
            </Button>
          </form>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {showSkeleton ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : analytics ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard
              label="Ready / Advanced"
              value={
                (analytics.readiness_states.ready ?? 0) +
                (analytics.readiness_states.advanced ?? 0)
              }
              hint="learners at node readiness"
            />
            <StatCard
              label="Evaluations finalized"
              value={analytics.evaluations.finalized ?? 0}
              hint={`${analytics.evaluations.pending ?? 0} pending`}
            />
            <StatCard
              label="Average grade"
              value={
                analytics.evaluations.average_grade != null
                  ? Math.round((analytics.evaluations.average_grade as number) * 100) / 100
                  : "—"
              }
            />
            <StatCard
              label="Publication candidates"
              value={analytics.publication_candidates}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Readiness states</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {Object.keys(READINESS_META).map((k) => (
                  <div key={k} className="flex items-center justify-between text-sm">
                    <span>{READINESS_META[k as keyof typeof READINESS_META].label}</span>
                    <Badge variant="secondary">{analytics.readiness_states[k] ?? 0}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Submissions & credits</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    Submissions by status
                  </p>
                  <CountRow counts={analytics.submissions_by_status} />
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    Mastery Credits
                  </p>
                  <CountRow
                    counts={{
                      recommended: Number(analytics.mastery_credits.recommended ?? 0),
                      approved: Number(analytics.mastery_credits.approved ?? 0),
                      redeemed: Number(analytics.mastery_credits.redeemed ?? 0),
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Publication candidates with SME verification */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <BadgeCheck className="size-4 text-muted-foreground" />
                <div>
                  <CardTitle className="text-base">Publication candidates</CardTitle>
                  <CardDescription>
                    {candidates.length} contribution(s) flagged for publication review.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {candidates.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
                  No publication candidates yet.
                </p>
              ) : (
                candidates.map((c) => (
                  <div
                    key={c.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{c.title ?? "Contribution"}</span>
                        <Badge variant="outline">{c.visibility_level}</Badge>
                        <Badge
                          variant={VERIFICATION_META[c.verification_status]?.variant ?? "outline"}
                        >
                          {VERIFICATION_META[c.verification_status]?.label ?? c.verification_status}
                        </Badge>
                      </div>
                      {c.summary && (
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {c.summary}
                        </p>
                      )}
                    </div>
                    {canVerify && c.verification_status !== "verified" && (
                      <div className="flex items-center gap-1.5">
                        <Button
                          size="xs"
                          onClick={onVerify(c.id, "verified", "public")}
                          disabled={busy === c.id}
                        >
                          {busy === c.id ? <Loader2 className="animate-spin" /> : <BadgeCheck />}
                          Verify
                        </Button>
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={onVerify(c.id, "needs_revision")}
                          disabled={busy === c.id}
                        >
                          Needs revision
                        </Button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {analytics.continuous_improvement && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Continuous improvement</CardTitle>
                <CardDescription>
                  Node friction, misconceptions, and rubric weaknesses to address.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <StageArtifactView artifact={analytics.continuous_improvement} />
              </CardContent>
            </Card>
          )}
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          Select a course to view its Blueprint analytics.
        </p>
      )}
    </div>
  );
}
