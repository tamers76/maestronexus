"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useEffect, useState } from "react";

import { AssessmentWorkflow } from "@/components/learn/assessment-workflow";
import { CreditsPanel } from "@/components/learn/credits-panel";
import { NextNodeCard } from "@/components/learn/next-node-card";
import { NodeEvidencePanel } from "@/components/learn/node-evidence-panel";
import { NodeStateBadge } from "@/components/learn/node-state-badge";
import { ReadinessStateBadge } from "@/components/learn/readiness-state-badge";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getNextNode, type NextNodeResponse } from "@/lib/adaptive";
import { ApiError } from "@/lib/api";
import { type ContributionAssessment, listAssessments } from "@/lib/blueprint";
import {
  completeNode,
  type EnrollmentDetail,
  type EnrollmentOut,
  getEnrollmentDetail,
  listCourses as listEnrollmentCourses,
  myEnrollments,
} from "@/lib/enrollment";
import { cn } from "@/lib/utils";

type Tab = "path" | "assessments" | "credits";

export function JourneyView() {
  const [enrollments, setEnrollments] = useState<EnrollmentOut[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<EnrollmentDetail | null>(null);
  const [rec, setRec] = useState<NextNodeResponse | null>(null);
  const [assessments, setAssessments] = useState<ContributionAssessment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyNode, setBusyNode] = useState<string | null>(null);
  const [expandedNode, setExpandedNode] = useState<string | null>(null);
  const [expandedAssessment, setExpandedAssessment] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("path");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const rows = await myEnrollments();
        if (!active) return;
        setEnrollments(rows);
        if (rows.length > 0) setSelectedId((prev) => prev ?? rows[0].id);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load enrollments.");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    (async () => {
      try {
        const [d, r] = await Promise.all([
          getEnrollmentDetail(selectedId),
          getNextNode(selectedId),
        ]);
        if (!active) return;
        setDetail(d);
        setRec(r);
        setError(null);
        // Resolve the owning course so we can load its contribution assessments.
        try {
          const courses = await listEnrollmentCourses();
          const course = courses.find((c) =>
            c.versions.some((v) => v.id === d.enrollment.course_version_id),
          );
          if (active && course) {
            const list = await listAssessments(course.id).catch(
              () => [] as ContributionAssessment[],
            );
            if (active) setAssessments(list);
          } else if (active) {
            setAssessments([]);
          }
        } catch {
          if (active) setAssessments([]);
        }
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load your journey.");
      }
    })();
    return () => {
      active = false;
    };
  }, [selectedId, reloadKey]);

  async function handleComplete(nodeId: string) {
    if (!selectedId) return;
    setBusyNode(nodeId);
    setError(null);
    try {
      await completeNode(selectedId, nodeId, { time_spent_seconds: 0 });
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not advance the node.");
    } finally {
      setBusyNode(null);
    }
  }

  if (enrollments === null) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (enrollments.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">My Journey</CardTitle>
          <CardDescription>
            You are not enrolled in any classes yet. Ask your teacher to enroll you.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const isStale = !detail || detail.enrollment.id !== selectedId;

  const tabs: { key: Tab; label: string }[] = [
    { key: "path", label: "Learning path" },
    { key: "assessments", label: `Assessments${assessments.length ? ` (${assessments.length})` : ""}` },
    { key: "credits", label: "Mastery Credits" },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Journey</h1>
        <p className="text-sm text-muted-foreground">
          Your adaptive Blueprint path — node readiness, evidence, formal
          assessments, and Mastery Credits.
        </p>
      </div>

      {enrollments.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {enrollments.map((e) => (
            <Button
              key={e.id}
              size="sm"
              variant={e.id === selectedId ? "default" : "outline"}
              onClick={() => setSelectedId(e.id)}
            >
              {e.class_id.slice(0, 8)}
            </Button>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      <NextNodeCard rec={rec} />

      <div className="flex overflow-hidden rounded-lg border border-border text-sm">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "px-3 py-1.5 transition-colors",
              tab === t.key ? "bg-muted font-medium" : "hover:bg-muted/40",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "path" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {detail ? detail.class_name : "Learning path"}
            </CardTitle>
            <CardDescription>
              {detail
                ? `${detail.nodes.filter((n) => n.state === "completed" || n.state === "mastered").length} of ${detail.nodes.length} nodes done — record evidence to advance readiness.`
                : "Loading nodes…"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isStale ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Node</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Readiness</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.nodes.map((n) => {
                    const open = expandedNode === n.node_id;
                    return (
                      <Fragment key={n.id}>
                        <TableRow>
                          <TableCell className="font-medium">
                            <button
                              type="button"
                              onClick={() => setExpandedNode(open ? null : n.node_id)}
                              className="flex items-center gap-1.5 text-left"
                            >
                              {open ? (
                                <ChevronDown className="size-3.5 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="size-3.5 text-muted-foreground" />
                              )}
                              {n.node_title}
                            </button>
                          </TableCell>
                          <TableCell className="text-muted-foreground">{n.node_type}</TableCell>
                          <TableCell>
                            <NodeStateBadge state={n.state} />
                          </TableCell>
                          <TableCell>
                            <ReadinessStateBadge state={n.readiness_state} />
                          </TableCell>
                          <TableCell className="text-right">
                            {n.state === "available" || n.state === "completed" ? (
                              <Button
                                size="xs"
                                variant="outline"
                                disabled={busyNode !== null}
                                onClick={() => handleComplete(n.node_id)}
                              >
                                {busyNode === n.node_id ? "Saving…" : "Advance"}
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TableCell>
                        </TableRow>
                        {open && (
                          <TableRow>
                            <TableCell colSpan={5} className="p-0">
                              {selectedId && (
                                <NodeEvidencePanel
                                  enrollmentId={selectedId}
                                  nodeId={n.node_id}
                                  onReadiness={() => setReloadKey((k) => k + 1)}
                                />
                              )}
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "assessments" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contribution assessments</CardTitle>
            <CardDescription>
              Personalize your context, pass the readiness gate, then submit your
              contribution for evaluation.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {assessments.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
                No contribution assessments are available for this course yet.
              </p>
            ) : (
              assessments.map((a) => {
                const open = expandedAssessment === a.id;
                return (
                  <div key={a.id} className="rounded-lg border border-border">
                    <button
                      type="button"
                      onClick={() => setExpandedAssessment(open ? null : a.id)}
                      className="flex w-full items-center justify-between gap-2 p-3 text-left"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-sm font-medium">{a.title}</span>
                          {typeof a.weight === "number" && (
                            <Badge variant="secondary">{a.weight}% weight</Badge>
                          )}
                        </div>
                        {a.contribution_purpose && (
                          <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                            {a.contribution_purpose}
                          </p>
                        )}
                      </div>
                      {open ? (
                        <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                      )}
                    </button>
                    {open && selectedId && (
                      <AssessmentWorkflow assessment={a} enrollmentId={selectedId} />
                    )}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      )}

      {tab === "credits" && selectedId && <CreditsPanel enrollmentId={selectedId} />}
    </div>
  );
}
