"use client";

import { BookOpen, GraduationCap, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { VersionPanel } from "@/components/courses/version-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Course,
  createCourse,
  deleteCourse,
  listCourses,
} from "@/lib/courses";

export default function CoursesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("course.manage");

  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      const page = await listCourses(100, 0);
      setCourses(page.items);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load courses.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!canManage) return;
    let active = true;
    (async () => {
      try {
        const page = await listCourses(100, 0);
        if (active) {
          setCourses(page.items);
          setError(null);
        }
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
  }, [canManage]);

  const onCreate = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!title.trim()) return;
      setCreating(true);
      setError(null);
      try {
        const course = await createCourse({
          title: title.trim(),
          description: description.trim() || null,
        });
        setTitle("");
        setDescription("");
        await load();
        setSelectedId(course.id);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not create the course.");
      } finally {
        setCreating(false);
      }
    },
    [title, description, load],
  );

  const onDelete = useCallback(
    async (course: Course) => {
      setError(null);
      try {
        await deleteCourse(course.id);
        if (selectedId === course.id) setSelectedId(null);
        await load();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not delete the course.");
      }
    },
    [load, selectedId],
  );

  const selected = courses.find((c) => c.id === selectedId) ?? null;

  if (!canManage) {
    return (
      <div className="mx-auto w-full max-w-3xl py-10">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Courses</CardTitle>
            <CardDescription>
              You don&apos;t have permission to manage courses.
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
          <GraduationCap className="size-5" />
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Courses</h1>
          <p className="text-sm text-muted-foreground">
            Create courses, manage versions, and publish learning graphs.
          </p>
        </div>
      </header>

      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        {/* Left: create + list */}
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">New course</CardTitle>
              <CardDescription>Start with a title; add a version next.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onCreate} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="course-title">Title</Label>
                  <Input
                    id="course-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Algebra Foundations"
                    required
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="course-desc">Description</Label>
                  <Textarea
                    id="course-desc"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Optional summary of what this course covers."
                  />
                </div>
                <Button type="submit" disabled={creating || !title.trim()}>
                  <Plus /> {creating ? "Creating…" : "Create course"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">All courses</CardTitle>
              <CardDescription>
                {loading ? "Loading…" : `${courses.length} course(s)`}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {loading ? (
                <>
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-16 w-full" />
                </>
              ) : courses.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  No courses yet. Create your first one.
                </div>
              ) : (
                courses.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedId(c.id)}
                    className={
                      "group flex items-start gap-3 rounded-lg border p-3 text-left transition-colors " +
                      (selectedId === c.id
                        ? "border-ring bg-muted/50"
                        : "border-border hover:bg-muted/40")
                    }
                  >
                    <BookOpen className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium">{c.title}</span>
                        <Badge
                          variant={c.status === "published" ? "success" : "secondary"}
                        >
                          {c.status}
                        </Badge>
                      </div>
                      {c.description && (
                        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                          {c.description}
                        </p>
                      )}
                    </div>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: selected course detail */}
        <div>
          {selected ? (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-lg">{selected.title}</CardTitle>
                    <CardDescription>
                      {selected.description || "No description."}
                    </CardDescription>
                  </div>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => onDelete(selected)}
                  >
                    <Trash2 /> Archive
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <VersionPanel
                  key={selected.id}
                  courseId={selected.id}
                  courseTitle={selected.title}
                />
              </CardContent>
            </Card>
          ) : (
            <Card className="flex h-full items-center justify-center">
              <CardContent className="py-16 text-center text-sm text-muted-foreground">
                Select a course to manage its versions and learning graph.
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
