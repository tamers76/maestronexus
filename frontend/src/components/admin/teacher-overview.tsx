"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatCard } from "@/components/admin/stat-card";
import { buttonVariants } from "@/components/ui/button";
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
import { type ClassSummary, listReportClasses } from "@/lib/analytics";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const QUICK_LINKS = [
  { href: "/teacher/classes", label: "Classes", hint: "Manage cohorts" },
  { href: "/teacher/attendance", label: "Attendance", hint: "Take attendance" },
  { href: "/teacher/grading", label: "Grading", hint: "Review submissions" },
];

export function TeacherOverview() {
  const { user } = useAuth();
  const [classes, setClasses] = useState<ClassSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const rows = await listReportClasses();
        if (active) setClasses(rows);
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Failed to load classes.");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const totalEnrolled = classes?.reduce((sum, c) => sum + c.enrollment_count, 0) ?? 0;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome{user ? `, ${user.display_name}` : ""}
        </h1>
        <p className="text-sm text-muted-foreground">
          Your classes at a glance and quick links to teaching tools.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="My classes" value={classes?.length ?? "—"} />
        <StatCard label="Total enrolled" value={classes ? totalEnrolled : "—"} />
        <StatCard
          label="Avg. class size"
          value={classes && classes.length > 0 ? Math.round(totalEnrolled / classes.length) : 0}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {QUICK_LINKS.map((q) => (
          <Card key={q.href}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="text-sm font-medium">{q.label}</p>
                <p className="text-xs text-muted-foreground">{q.hint}</p>
              </div>
              <Link href={q.href} className={buttonVariants({ variant: "outline", size: "sm" })}>
                Open
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">My classes</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!classes ? (
            <div className="p-4">
              <Skeleton className="h-40 w-full" />
            </div>
          ) : classes.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">
              You have no classes assigned yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Class</TableHead>
                  <TableHead>Course</TableHead>
                  <TableHead className="text-right">Enrolled</TableHead>
                  <TableHead className="text-right">Report</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {classes.map((c) => (
                  <TableRow key={c.class_id}>
                    <TableCell className="font-medium">{c.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {c.course_title ?? "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {c.enrollment_count}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href="/admin/reports"
                        className={buttonVariants({ variant: "outline", size: "xs" })}
                      >
                        View
                      </Link>
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
