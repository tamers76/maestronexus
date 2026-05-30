"use client";

import { useEffect, useState } from "react";

import { NextNodeCard } from "@/components/learn/next-node-card";
import { NodeStateBadge } from "@/components/learn/node-state-badge";
import { ReadinessStateBadge } from "@/components/learn/readiness-state-badge";
import { EnrollmentSubmissions } from "@/components/faculty/enrollment-submissions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getNextNode, type NextNodeResponse, overrideNextNode } from "@/lib/adaptive";
import { ApiError } from "@/lib/api";
import { type EnrollmentDetail, getEnrollmentDetail } from "@/lib/enrollment";

/**
 * Teacher view of one learner's progress: node states, the engine's current
 * recommendation, and a control to override the next node (override wins).
 */
export function LearnerProgress({ enrollmentId }: { enrollmentId: string }) {
  const [detail, setDetail] = useState<EnrollmentDetail | null>(null);
  const [rec, setRec] = useState<NextNodeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overrideNode, setOverrideNode] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [d, r] = await Promise.all([
          getEnrollmentDetail(enrollmentId),
          getNextNode(enrollmentId),
        ]);
        if (!active) return;
        setDetail(d);
        setRec(r);
        setError(null);
        setOverrideNode((prev) => prev || (d.nodes[0]?.node_id ?? ""));
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load learner progress.");
      }
    })();
    return () => {
      active = false;
    };
  }, [enrollmentId, reloadKey]);

  async function handleOverride(e: React.FormEvent) {
    e.preventDefault();
    if (!overrideNode) return;
    setSaving(true);
    setError(null);
    try {
      await overrideNextNode(enrollmentId, {
        node_id: overrideNode,
        reason: overrideReason || null,
      });
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not assign the node.");
    } finally {
      setSaving(false);
    }
  }

  const isStale = !detail || detail.enrollment.id !== enrollmentId;
  if (isStale) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <NextNodeCard rec={rec} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{detail.learner_name || "Learner"}</CardTitle>
          <CardDescription className="flex flex-wrap items-center gap-2">
            <span>
              {detail.nodes.filter((n) => n.state === "completed" || n.state === "mastered").length}{" "}
              of {detail.nodes.length} nodes done
            </span>
            {(() => {
              const needs = detail.nodes.filter(
                (n) => n.readiness_state === "not_ready" || n.readiness_state === "partially_ready",
              ).length;
              return needs > 0 ? (
                <Badge variant="warning">{needs} node(s) need support</Badge>
              ) : null;
            })()}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Node</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Readiness</TableHead>
                <TableHead>Attempts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.nodes.map((n) => (
                <TableRow key={n.id}>
                  <TableCell className="font-medium">{n.node_title}</TableCell>
                  <TableCell className="text-muted-foreground">{n.node_type}</TableCell>
                  <TableCell>
                    <NodeStateBadge state={n.state} />
                  </TableCell>
                  <TableCell>
                    <ReadinessStateBadge state={n.readiness_state} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{n.attempts}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Assign next node (override)</CardTitle>
          <CardDescription>A teacher assignment overrides the engine.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleOverride} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="override-node">Node</Label>
              <select
                id="override-node"
                value={overrideNode}
                onChange={(e) => setOverrideNode(e.target.value)}
                className="h-9 rounded-lg border border-border bg-background px-3 text-sm"
              >
                {detail.nodes.map((n) => (
                  <option key={n.node_id} value={n.node_id}>
                    {n.node_title}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="override-reason">Reason (optional)</Label>
              <input
                id="override-reason"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Why this node?"
                className="h-9 rounded-lg border border-border bg-background px-3 text-sm"
              />
            </div>
            <Button type="submit" size="sm" disabled={saving || !overrideNode}>
              {saving ? "Assigning…" : "Assign"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <EnrollmentSubmissions key={enrollmentId} enrollmentId={enrollmentId} />
    </div>
  );
}
