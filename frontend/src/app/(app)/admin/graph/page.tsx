"use client";

import { useSearchParams } from "next/navigation";
import { Network, Workflow } from "lucide-react";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { GraphEditor } from "@/components/courses/graph-editor";
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
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Course,
  type CourseVersion,
  listCourses,
  listVersions,
} from "@/lib/courses";

const CANVAS_HEIGHT = "h-[calc(100vh-6.5rem)]";

function selectClass() {
  return "flex h-9 w-full rounded-lg border border-border bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50";
}

function VersionPicker({
  onPick,
}: {
  onPick: (versionId: string, courseTitle: string) => void;
}) {
  const [courses, setCourses] = useState<Course[]>([]);
  const [versions, setVersions] = useState<CourseVersion[]>([]);
  const [courseId, setCourseId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const page = await listCourses(100, 0);
        if (active) setCourses(page.items);
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
  }, []);

  useEffect(() => {
    if (!courseId) return;
    let active = true;
    (async () => {
      try {
        const vs = await listVersions(courseId);
        if (active) {
          setVersions(vs);
          setVersionId(vs[0]?.id ?? "");
        }
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load versions.");
      }
    })();
    return () => {
      active = false;
    };
  }, [courseId]);

  const courseTitle = useMemo(
    () => courses.find((c) => c.id === courseId)?.title ?? "",
    [courses, courseId],
  );

  return (
    <div className="mx-auto w-full max-w-xl py-10">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Open the learning graph</CardTitle>
          <CardDescription>
            Pick a course version to edit its node-and-edge graph.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {loading ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="picker-course">Course</Label>
                <select
                  id="picker-course"
                  className={selectClass()}
                  value={courseId}
                  onChange={(e) => {
                    setCourseId(e.target.value);
                    setVersions([]);
                    setVersionId("");
                  }}
                >
                  <option value="">Select a course…</option>
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="picker-version">Version</Label>
                <select
                  id="picker-version"
                  className={selectClass()}
                  value={versionId}
                  onChange={(e) => setVersionId(e.target.value)}
                  disabled={!courseId || versions.length === 0}
                >
                  {versions.length === 0 ? (
                    <option value="">No versions — create one on the Courses page</option>
                  ) : (
                    versions.map((v) => (
                      <option key={v.id} value={v.id}>
                        v{v.version} · {v.state}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <Button
                disabled={!versionId}
                onClick={() => onPick(versionId, courseTitle)}
              >
                <Network /> Open editor
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function GraphContent() {
  const params = useSearchParams();
  const [versionId, setVersionId] = useState<string | null>(() => params.get("version"));
  const [courseTitle, setCourseTitle] = useState<string>(() => params.get("course") ?? "");

  const onPick = useCallback((id: string, title: string) => {
    setVersionId(id);
    setCourseTitle(title);
  }, []);

  if (!versionId) return <VersionPicker onPick={onPick} />;

  return (
    <div className="-mx-4 -my-6 md:-mx-8">
      <div className={`${CANVAS_HEIGHT} overflow-hidden border-border`}>
        <GraphEditor
          key={versionId}
          versionId={versionId}
          courseTitle={courseTitle || undefined}
        />
      </div>
    </div>
  );
}

export default function GraphEditorPage() {
  const { hasPermission } = useAuth();

  if (!hasPermission("graph.manage")) {
    return (
      <div className="mx-auto w-full max-w-3xl py-10">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Workflow className="size-5 text-muted-foreground" />
              <CardTitle className="text-xl">Learning Graph</CardTitle>
            </div>
            <CardDescription>
              You don&apos;t have permission to edit the learning graph.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <Suspense fallback={<Skeleton className="h-[60vh] w-full" />}>
      <GraphContent />
    </Suspense>
  );
}
