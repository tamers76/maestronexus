"use client";

import Link from "next/link";
import { GitBranch, Network, Plus, Rocket } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  type CourseVersion,
  createVersion,
  listVersions,
  publishVersion,
} from "@/lib/courses";

function stateVariant(state: string): "success" | "secondary" {
  return state === "published" ? "success" : "secondary";
}

export function VersionPanel({
  courseId,
  courseTitle,
}: {
  courseId: string;
  courseTitle: string;
}) {
  const [versions, setVersions] = useState<CourseVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setVersions(await listVersions(courseId));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load versions.");
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const vs = await listVersions(courseId);
        if (active) {
          setVersions(vs);
          setError(null);
        }
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load versions.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [courseId]);

  const onCreate = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await createVersion(courseId, true);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create a version.");
    } finally {
      setBusy(false);
    }
  }, [courseId, load]);

  const onPublish = useCallback(
    async (versionId: string) => {
      setBusy(true);
      setError(null);
      try {
        await publishVersion(versionId);
        await load();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not publish.");
      } finally {
        setBusy(false);
      }
    },
    [load],
  );

  const graphHref = (versionId: string) =>
    `/admin/graph?version=${versionId}&course=${encodeURIComponent(courseTitle)}`;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch className="size-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">Versions</h3>
        </div>
        <Button size="sm" variant="outline" onClick={onCreate} disabled={busy}>
          <Plus /> New version
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading ? (
        <Skeleton className="h-24 w-full" />
      ) : versions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          No versions yet. Create one to start building the learning graph.
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Version</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Published</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {versions.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-medium">v{v.version}</TableCell>
                <TableCell>
                  <Badge variant={stateVariant(v.state)}>{v.state}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {v.published_at ? new Date(v.published_at).toLocaleDateString() : "—"}
                </TableCell>
                <TableCell>
                  <div className="flex items-center justify-end gap-2">
                    <Button size="xs" variant="outline" render={<Link href={graphHref(v.id)} />}>
                      <Network /> Editor
                    </Button>
                    {v.state !== "published" && (
                      <Button
                        size="xs"
                        onClick={() => onPublish(v.id)}
                        disabled={busy}
                      >
                        <Rocket /> Publish
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
