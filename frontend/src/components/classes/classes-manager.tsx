"use client";

import { useEffect, useState } from "react";

import { ClassRoster } from "@/components/classes/class-roster";
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
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type ClassOut,
  type CourseOut,
  createClass,
  listClasses,
  listCourses,
} from "@/lib/enrollment";

export function ClassesManager() {
  const { user } = useAuth();
  const [courses, setCourses] = useState<CourseOut[] | null>(null);
  const [classes, setClasses] = useState<ClassOut[] | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [courseId, setCourseId] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const userId = user?.id;

  useEffect(() => {
    if (!userId) return;
    let active = true;
    (async () => {
      try {
        const [c, page] = await Promise.all([listCourses(), listClasses(userId)]);
        if (!active) return;
        setCourses(c);
        setCourseId((prev) => prev || (c[0]?.id ?? ""));
        setClasses(page.items);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load classes.");
      }
    })();
    return () => {
      active = false;
    };
  }, [userId, reloadKey]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!courseId || !name.trim() || !userId) return;
    setSaving(true);
    setError(null);
    try {
      const created = await createClass({
        course_id: courseId,
        name: name.trim(),
        teacher_id: userId,
      });
      setName("");
      setSelectedClassId(created.id);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the class.");
    } finally {
      setSaving(false);
    }
  }

  const selectedClass = classes?.find((c) => c.id === selectedClassId) ?? null;
  const selectedVersions =
    courses?.find((c) => c.id === selectedClass?.course_id)?.versions ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Classes</h1>
        <p className="text-sm text-muted-foreground">
          Manage your cohorts, enroll learners, and review progress.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Create a class</CardTitle>
          <CardDescription>Pick a course and name the cohort.</CardDescription>
        </CardHeader>
        <CardContent>
          {courses === null ? (
            <Skeleton className="h-9 w-full" />
          ) : courses.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No courses exist yet. A course designer must create one first.
            </p>
          ) : (
            <form onSubmit={handleCreate} className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="course">Course</Label>
                <select
                  id="course"
                  value={courseId}
                  onChange={(e) => setCourseId(e.target.value)}
                  className="h-9 rounded-lg border border-border bg-background px-3 text-sm"
                >
                  {courses.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-1 flex-col gap-1.5">
                <Label htmlFor="class-name">Class name</Label>
                <Input
                  id="class-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Fall 2026 — Section A"
                  required
                />
              </div>
              <Button type="submit" size="sm" disabled={saving}>
                {saving ? "Creating…" : "Create"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your classes</CardTitle>
          <CardDescription>Select a class to manage its roster.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {classes === null ? (
            <Skeleton className="h-9 w-full" />
          ) : classes.length === 0 ? (
            <p className="text-sm text-muted-foreground">You have no classes yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {classes.map((c) => (
                <Button
                  key={c.id}
                  size="sm"
                  variant={c.id === selectedClassId ? "default" : "outline"}
                  onClick={() => setSelectedClassId(c.id)}
                >
                  {c.name}
                </Button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {selectedClass && <ClassRoster classId={selectedClass.id} versions={selectedVersions} />}
    </div>
  );
}
