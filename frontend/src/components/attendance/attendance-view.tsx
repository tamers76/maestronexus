"use client";

import { useEffect, useState } from "react";

import { StatusSelector } from "@/components/attendance/status-selector";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { ApiError } from "@/lib/api";
import {
  type AttendanceSession,
  type AttendanceStatus,
  type ClassInfo,
  createSession,
  getRoster,
  listClasses,
  listSessions,
  markRecords,
  type RosterEntry,
  type SessionMode,
} from "@/lib/attendance";

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function AttendanceView() {
  const [classes, setClasses] = useState<ClassInfo[] | null>(null);
  const [classId, setClassId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<AttendanceSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [roster, setRoster] = useState<RosterEntry[] | null>(null);
  const [marks, setMarks] = useState<Record<string, AttendanceStatus>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // New-session form state.
  const [newWhen, setNewWhen] = useState<string>("");
  const [newMode, setNewMode] = useState<SessionMode>("in_person");
  const [creating, setCreating] = useState(false);

  // Reload counters let event handlers trigger effect re-fetches.
  const [sessionsReload, setSessionsReload] = useState(0);
  const [rosterReload, setRosterReload] = useState(0);

  // Bootstrap: load the caller's classes.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const rows = await listClasses();
        if (active) {
          setClasses(rows);
          if (rows.length > 0) setClassId(rows[0].id);
        }
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load your classes.");
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Sessions for the selected class.
  useEffect(() => {
    if (!classId) return;
    let active = true;
    (async () => {
      try {
        const page = await listSessions({ class_id: classId, limit: 100 });
        if (active) setSessions(page.items);
      } catch (err) {
        if (active) {
          setError(err instanceof ApiError ? err.message : "Failed to load sessions.");
          setSessions([]);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [classId, sessionsReload]);

  // Roster + existing marks for the selected session.
  useEffect(() => {
    if (!sessionId) return;
    let active = true;
    (async () => {
      try {
        const entries = await getRoster(sessionId);
        if (!active) return;
        const initial: Record<string, AttendanceStatus> = {};
        for (const e of entries) {
          if (e.status) initial[e.learner_id] = e.status as AttendanceStatus;
        }
        setRoster(entries);
        setMarks(initial);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load the roster.");
      }
    })();
    return () => {
      active = false;
    };
  }, [sessionId, rosterReload]);

  function selectClass(id: string) {
    setClassId(id);
    setSessionId(null);
    setRoster(null);
    setSaved(false);
  }

  function selectSession(id: string) {
    setSessionId(id);
    setSaved(false);
  }

  async function onCreateSession(e: React.FormEvent) {
    e.preventDefault();
    if (!classId || !newWhen) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createSession({
        class_id: classId,
        scheduled_at: new Date(newWhen).toISOString(),
        mode: newMode,
      });
      setNewWhen("");
      setSessionsReload((k) => k + 1);
      selectSession(created.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the session.");
    } finally {
      setCreating(false);
    }
  }

  async function onSaveMarks() {
    if (!sessionId || !roster) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const records = roster
        .filter((e) => marks[e.learner_id])
        .map((e) => ({ learner_id: e.learner_id, status: marks[e.learner_id] }));
      await markRecords(sessionId, records);
      setSaved(true);
      setRosterReload((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save attendance.");
    } finally {
      setSaving(false);
    }
  }

  if (classes === null) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Attendance</h1>
        <p className="text-sm text-muted-foreground">
          Create a session for one of your classes and mark each learner.
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {classes.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No classes</CardTitle>
            <CardDescription>
              You do not teach any classes yet. Once a class is assigned to you it will appear
              here.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <>
          {/* Class selection */}
          <div className="flex flex-wrap gap-2">
            {classes.map((c) => (
              <Button
                key={c.id}
                size="sm"
                variant={c.id === classId ? "default" : "outline"}
                onClick={() => selectClass(c.id)}
              >
                {c.name}
              </Button>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
            {/* Sessions + create */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Sessions</CardTitle>
                <CardDescription>Select a session or create a new one.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <form onSubmit={onCreateSession} className="flex flex-col gap-3">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="when">Scheduled time</Label>
                    <Input
                      id="when"
                      type="datetime-local"
                      value={newWhen}
                      onChange={(e) => setNewWhen(e.target.value)}
                      required
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="mode">Mode</Label>
                    <select
                      id="mode"
                      value={newMode}
                      onChange={(e) => setNewMode(e.target.value as SessionMode)}
                      className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm shadow-sm"
                    >
                      <option value="in_person">In person</option>
                      <option value="online">Online</option>
                      <option value="hybrid">Hybrid</option>
                    </select>
                  </div>
                  <Button type="submit" size="sm" disabled={creating}>
                    {creating ? "Creating…" : "Create session"}
                  </Button>
                </form>

                <div className="flex flex-col gap-1.5">
                  {sessions.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No sessions yet.</p>
                  ) : (
                    sessions.map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => selectSession(s.id)}
                        className={
                          "flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition-colors " +
                          (s.id === sessionId
                            ? "border-ring bg-muted/60"
                            : "border-border hover:bg-muted/40")
                        }
                      >
                        <span>{formatWhen(s.scheduled_at)}</span>
                        <span className="text-xs text-muted-foreground">{s.mode}</span>
                      </button>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Roster marking */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base">Mark attendance</CardTitle>
                  {saved && <span className="text-sm text-emerald-600">Saved</span>}
                </div>
                <CardDescription>
                  {sessionId
                    ? "Set each learner's status, then save."
                    : "Select a session to mark attendance."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!sessionId ? (
                  <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                    No session selected.
                  </div>
                ) : roster === null ? (
                  <Skeleton className="h-48 w-full" />
                ) : roster.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                    No learners enrolled in this class yet.
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Learner</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {roster.map((e) => (
                          <TableRow key={e.learner_id}>
                            <TableCell>
                              <div className="font-medium">{e.display_name}</div>
                              <div className="text-xs text-muted-foreground">{e.email}</div>
                            </TableCell>
                            <TableCell>
                              <StatusSelector
                                value={marks[e.learner_id] ?? null}
                                onChange={(status) =>
                                  setMarks((prev) => ({ ...prev, [e.learner_id]: status }))
                                }
                                disabled={saving}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    <div>
                      <Button onClick={onSaveMarks} disabled={saving}>
                        {saving ? "Saving…" : "Save attendance"}
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
