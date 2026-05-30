"use client";

import { useEffect, useState } from "react";

import { LearnerProgress } from "@/components/classes/learner-progress";
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
import { ApiError } from "@/lib/api";
import {
  type CourseVersionOut,
  type EnrollmentOut,
  enrollLearner,
  listEnrollments,
} from "@/lib/enrollment";

export function ClassRoster({
  classId,
  versions,
}: {
  classId: string;
  versions: CourseVersionOut[];
}) {
  const [enrollments, setEnrollments] = useState<EnrollmentOut[] | null>(null);
  const [loadedClassId, setLoadedClassId] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [versionId, setVersionId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const page = await listEnrollments({ class_id: classId });
        if (!active) return;
        setEnrollments(page.items);
        setLoadedClassId(classId);
        setSelected((prev) => (page.items.some((e) => e.id === prev) ? prev : null));
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load enrollments.");
      }
    })();
    return () => {
      active = false;
    };
  }, [classId, reloadKey]);

  async function handleEnroll(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await enrollLearner({
        class_id: classId,
        email: email.trim(),
        course_version_id: versionId || null,
      });
      setEmail("");
      setNotice("Learner enrolled.");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not enroll the learner.");
    } finally {
      setSaving(false);
    }
  }

  const loading = enrollments === null || loadedClassId !== classId;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Enroll a learner</CardTitle>
          <CardDescription>Enrollment pins the learner to a course version.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleEnroll} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex flex-1 flex-col gap-1.5">
              <Label htmlFor="enroll-email">Learner email</Label>
              <Input
                id="enroll-email"
                type="email"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                placeholder="learner@the-code.dev"
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="enroll-version">Version</Label>
              <select
                id="enroll-version"
                value={versionId}
                onChange={(ev) => setVersionId(ev.target.value)}
                className="h-9 rounded-lg border border-border bg-background px-3 text-sm"
              >
                <option value="">Latest published</option>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version} ({v.state})
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" size="sm" disabled={saving}>
              {saving ? "Enrolling…" : "Enroll"}
            </Button>
          </form>
          {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
          {notice && (
            <p className="mt-2 text-sm text-emerald-600 dark:text-emerald-400">{notice}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Enrolled learners</CardTitle>
          <CardDescription>Select a learner to view progress.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : enrollments && enrollments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No learners enrolled yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {enrollments?.map((e) => (
                <Button
                  key={e.id}
                  size="sm"
                  variant={e.id === selected ? "default" : "outline"}
                  onClick={() => setSelected(e.id)}
                >
                  {e.user_id.slice(0, 8)} · {e.status}
                </Button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {selected && <LearnerProgress enrollmentId={selected} />}
    </div>
  );
}
