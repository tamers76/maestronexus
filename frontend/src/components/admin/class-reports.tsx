"use client";

import { useEffect, useState } from "react";

import { PercentBar } from "@/components/admin/percent-bar";
import { StatCard } from "@/components/admin/stat-card";
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
import { ApiError } from "@/lib/api";
import {
  type ClassReport,
  type ClassSummary,
  getClassReport,
  listReportClasses,
} from "@/lib/analytics";

export function ClassReports({
  title = "Reports",
  description = "Class-level enrollment, progress, and attendance.",
}: {
  title?: string;
  description?: string;
}) {
  const [classes, setClasses] = useState<ClassSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [report, setReport] = useState<ClassReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const rows = await listReportClasses();
        if (!active) return;
        setClasses(rows);
        if (rows.length > 0) setSelected(rows[0].class_id);
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Failed to load classes.");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let active = true;
    (async () => {
      try {
        const r = await getClassReport(selected);
        if (active) setReport(r);
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Failed to load report.");
      }
    })();
    return () => {
      active = false;
    };
  }, [selected]);

  // Derived loading avoids resetting state synchronously inside the effect.
  const reportLoading = !report || report.class_id !== selected;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!classes ? (
        <Skeleton className="h-32 w-full" />
      ) : classes.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No classes</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            There are no classes available for you to report on yet.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="text-base">Classes</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1 p-2">
              {classes.map((c) => (
                <button
                  key={c.class_id}
                  onClick={() => setSelected(c.class_id)}
                  className={
                    c.class_id === selected
                      ? "flex flex-col items-start rounded-lg bg-muted px-3 py-2 text-left"
                      : "flex flex-col items-start rounded-lg px-3 py-2 text-left hover:bg-muted/60"
                  }
                >
                  <span className="text-sm font-medium">{c.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {c.course_title ?? "—"} · {c.enrollment_count} enrolled
                  </span>
                </button>
              ))}
            </CardContent>
          </Card>

          <div className="flex flex-col gap-4">
            {reportLoading || !report ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <ReportDetail report={report} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ReportDetail({ report }: { report: ClassReport }) {
  return (
    <>
      <div>
        <h2 className="text-lg font-semibold tracking-tight">{report.name}</h2>
        <p className="text-sm text-muted-foreground">{report.course_title ?? "No course"}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Enrolled" value={report.enrollment_count} />
        <StatCard label="Active" value={report.active_enrollment_count} />
        <StatCard
          label="Nodes done"
          value={`${report.completed_nodes}/${report.total_nodes}`}
        />
        <StatCard label="Attendance recs" value={report.attendance_records} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Outcomes</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <PercentBar label="Node completion" value={report.avg_completion_pct} />
          <PercentBar label="Attendance rate" value={report.attendance_rate} />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Metric</TableHead>
                <TableHead className="text-right">Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>Total enrollments</TableCell>
                <TableCell className="text-right tabular-nums">
                  {report.enrollment_count}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Active enrollments</TableCell>
                <TableCell className="text-right tabular-nums">
                  {report.active_enrollment_count}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Completed nodes</TableCell>
                <TableCell className="text-right tabular-nums">
                  {report.completed_nodes} / {report.total_nodes}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Avg. completion</TableCell>
                <TableCell className="text-right tabular-nums">
                  {report.avg_completion_pct}%
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Attendance rate</TableCell>
                <TableCell className="text-right tabular-nums">
                  {report.attendance_rate}%
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
