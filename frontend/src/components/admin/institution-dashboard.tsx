"use client";

import { useEffect, useState } from "react";

import { PercentBar } from "@/components/admin/percent-bar";
import { StatCard } from "@/components/admin/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getInstitutionDashboard, type InstitutionDashboard } from "@/lib/analytics";
import { ApiError } from "@/lib/api";

export function InstitutionDashboardView() {
  const [data, setData] = useState<InstitutionDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const d = await getInstitutionDashboard();
        if (active) setData(d);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load the dashboard.");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Institution Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Platform-wide totals, engagement, and completion across your institution.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!data ? (
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Users" value={data.totals.users} />
            <StatCard label="Courses" value={data.totals.courses} />
            <StatCard label="Classes" value={data.totals.classes} />
            <StatCard
              label="Enrollments"
              value={data.totals.enrollments}
              hint={`${data.engagement.active_enrollments} active`}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle className="text-base">Engagement</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <PercentBar
                  label="Avg. node completion"
                  value={data.engagement.avg_completion_pct}
                />
                <PercentBar label="Attendance rate" value={data.engagement.attendance_rate} />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Active enrollments</span>
                  <span className="font-medium tabular-nums">
                    {data.engagement.active_enrollments} / {data.totals.enrollments}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Top classes by enrollment</CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_classes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No classes yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Class</TableHead>
                        <TableHead>Course</TableHead>
                        <TableHead className="text-right">Enrollments</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {data.top_classes.map((c) => (
                        <TableRow key={c.class_id}>
                          <TableCell className="font-medium">{c.name}</TableCell>
                          <TableCell className="text-muted-foreground">
                            {c.course_title ?? "—"}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {c.enrollment_count}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Users by role</CardTitle>
            </CardHeader>
            <CardContent>
              {data.users_by_role.length === 0 ? (
                <p className="text-sm text-muted-foreground">No role assignments yet.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {data.users_by_role.map((r) => (
                    <Badge key={r.role} variant="secondary" className="gap-1.5">
                      {r.role}
                      <span className="rounded bg-background/60 px-1 tabular-nums">
                        {r.count}
                      </span>
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
