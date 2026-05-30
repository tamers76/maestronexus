"use client";

import {
  BookOpen,
  FileText,
  GraduationCap,
  Loader2,
  Plus,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { BlueprintCoursePanel } from "@/components/courses/blueprint-course-panel";
import { ClosPanel } from "@/components/courses/clos-panel";
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
  createCourseFromForm,
  createCourseFromSyllabus,
  deleteCourse,
  listCourses,
} from "@/lib/courses";

const ACCEPTED = ".pdf,.docx,.doc,.txt,.md";
const VALID_EXT = [".pdf", ".docx", ".doc", ".txt", ".md"];

type Tab = "upload" | "manual";

export default function CoursesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("course.manage");

  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [tab, setTab] = useState<Tab>("upload");

  // Upload tab
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  // Manual tab
  const [courseCode, setCourseCode] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creditHours, setCreditHours] = useState(3);
  const [clos, setClos] = useState<string[]>([""]);
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

  const handleFile = useCallback(
    async (file: File) => {
      const lower = file.name.toLowerCase();
      if (!VALID_EXT.some((ext) => lower.endsWith(ext))) {
        setError("Please upload a PDF, DOCX, or text syllabus.");
        return;
      }
      setUploading(true);
      setError(null);
      try {
        const result = await createCourseFromSyllabus(file);
        await load();
        setSelectedId(result.course.id);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Failed to process the syllabus.",
        );
      } finally {
        setUploading(false);
      }
    },
    [load],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  const onManualSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!title.trim()) return;
      const validClos = clos.map((c) => c.trim()).filter(Boolean);
      setCreating(true);
      setError(null);
      try {
        const result = await createCourseFromForm({
          title: title.trim(),
          description: description.trim() || null,
          course_code: courseCode.trim() || null,
          credit_hours: creditHours,
          clos: validClos,
        });
        setCourseCode("");
        setTitle("");
        setDescription("");
        setCreditHours(3);
        setClos([""]);
        await load();
        setSelectedId(result.course.id);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not create the course.");
      } finally {
        setCreating(false);
      }
    },
    [title, description, courseCode, creditHours, clos, load],
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
            Turn a syllabus into a course, refine its outcomes, and publish learning graphs.
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
              <CardDescription>
                Upload a syllabus to auto-extract outcomes, or enter details manually.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="inline-flex rounded-lg border border-border p-0.5 text-sm">
                <button
                  type="button"
                  onClick={() => setTab("upload")}
                  className={
                    "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 transition-colors " +
                    (tab === "upload"
                      ? "bg-muted font-medium"
                      : "text-muted-foreground hover:bg-muted/50")
                  }
                >
                  <Upload className="size-4" /> Upload syllabus
                </button>
                <button
                  type="button"
                  onClick={() => setTab("manual")}
                  className={
                    "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 transition-colors " +
                    (tab === "manual"
                      ? "bg-muted font-medium"
                      : "text-muted-foreground hover:bg-muted/50")
                  }
                >
                  <FileText className="size-4" /> Manual entry
                </button>
              </div>

              {tab === "upload" ? (
                <div
                  role="button"
                  tabIndex={0}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={onDrop}
                  onClick={() => {
                    if (!uploading) fileInputRef.current?.click();
                  }}
                  onKeyDown={(e) => {
                    if ((e.key === "Enter" || e.key === " ") && !uploading) {
                      e.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                  className={
                    "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors " +
                    (dragOver
                      ? "border-ring bg-muted/50"
                      : "border-border hover:bg-muted/40")
                  }
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ACCEPTED}
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) void handleFile(file);
                      e.target.value = "";
                    }}
                  />
                  {uploading ? (
                    <>
                      <Loader2 className="size-6 animate-spin text-primary" />
                      <p className="text-sm font-medium">Processing syllabus…</p>
                      <p className="text-xs text-muted-foreground">
                        Extracting course details and CLOs. This may take a minute.
                      </p>
                    </>
                  ) : (
                    <>
                      <Upload className="size-6 text-muted-foreground" />
                      <p className="text-sm font-medium">
                        Drop your syllabus here or click to browse
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Supports PDF, DOCX, and text files.
                      </p>
                    </>
                  )}
                </div>
              ) : (
                <form onSubmit={onManualSubmit} className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="course-code">Course code</Label>
                      <Input
                        id="course-code"
                        value={courseCode}
                        onChange={(e) => setCourseCode(e.target.value)}
                        placeholder="e.g. MDLD602"
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="credit-hours">Credit hours</Label>
                      <Input
                        id="credit-hours"
                        type="number"
                        min={0}
                        value={creditHours}
                        onChange={(e) =>
                          setCreditHours(parseInt(e.target.value, 10) || 0)
                        }
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="course-title">Title</Label>
                    <Input
                      id="course-title"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="e.g. Curriculum Design Foundations"
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
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <Label>Course Learning Outcomes</Label>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setClos((prev) => [...prev, ""])}
                      >
                        <Plus /> Add CLO
                      </Button>
                    </div>
                    <div className="flex flex-col gap-2">
                      {clos.map((clo, index) => (
                        <div key={index} className="flex items-center gap-2">
                          <Badge variant="secondary" className="font-mono">
                            {index + 1}
                          </Badge>
                          <Input
                            value={clo}
                            onChange={(e) =>
                              setClos((prev) =>
                                prev.map((c, i) => (i === index ? e.target.value : c)),
                              )
                            }
                            placeholder="Learners will be able to…"
                            className="flex-1"
                          />
                          {clos.length > 1 && (
                            <Button
                              type="button"
                              size="icon"
                              variant="ghost"
                              onClick={() =>
                                setClos((prev) => prev.filter((_, i) => i !== index))
                              }
                            >
                              <X />
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                  <Button type="submit" disabled={creating || !title.trim()}>
                    {creating ? <Loader2 className="animate-spin" /> : <Plus />}
                    {creating ? "Creating…" : "Create course"}
                  </Button>
                </form>
              )}
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
                        {c.course_code && (
                          <Badge variant="outline" className="font-mono">
                            {c.course_code}
                          </Badge>
                        )}
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
        <div className="flex flex-col gap-6">
          {selected ? (
            <>
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

              <ClosPanel key={`clos-${selected.id}`} courseId={selected.id} />

              <BlueprintCoursePanel
                key={`bp-${selected.id}`}
                courseId={selected.id}
                creditHours={selected.credit_hours}
              />
            </>
          ) : (
            <Card className="flex h-full items-center justify-center">
              <CardContent className="py-16 text-center text-sm text-muted-foreground">
                Select a course to manage its outcomes, versions, and learning graph.
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
