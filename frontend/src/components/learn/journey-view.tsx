"use client";

import { useEffect, useState } from "react";

import { NextNodeCard } from "@/components/learn/next-node-card";
import { NodeStateBadge } from "@/components/learn/node-state-badge";
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
import {
  completeNode,
  type EnrollmentDetail,
  type EnrollmentOut,
  getEnrollmentDetail,
  myEnrollments,
} from "@/lib/enrollment";

export function JourneyView() {
  const [enrollments, setEnrollments] = useState<EnrollmentOut[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<EnrollmentDetail | null>(null);
  const [rec, setRec] = useState<NextNodeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyNode, setBusyNode] = useState<string | null>(null);
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
      setError(err instanceof ApiError ? err.message : "Could not mark the node complete.");
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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Journey</h1>
        <p className="text-sm text-muted-foreground">
          Your adaptive learning path — node states and what to do next.
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

      <NextNodeCard rec={rec} onComplete={handleComplete} busy={busyNode !== null} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {detail ? detail.class_name : "Learning path"}
          </CardTitle>
          <CardDescription>
            {detail
              ? `${detail.nodes.filter((n) => n.state === "completed" || n.state === "mastered").length} of ${detail.nodes.length} nodes done`
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
                  <TableHead>Attempts</TableHead>
                  <TableHead className="text-right">Action</TableHead>
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
                    <TableCell className="text-muted-foreground">{n.attempts}</TableCell>
                    <TableCell className="text-right">
                      {n.state === "available" ? (
                        <Button
                          size="xs"
                          disabled={busyNode !== null}
                          onClick={() => handleComplete(n.node_id)}
                        >
                          {busyNode === n.node_id ? "Saving…" : "Mark complete"}
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
