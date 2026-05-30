"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { type AuditLog, listAuditLogs } from "@/lib/iam";

const PAGE_SIZE = 25;

function fmt(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString();
}

export function AuditLogView() {
  const [logs, setLogs] = useState<AuditLog[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  // Draft inputs vs. the committed filters that actually drive the query.
  const [action, setAction] = useState("");
  const [objectType, setObjectType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [filters, setFilters] = useState({ action: "", objectType: "", dateFrom: "" });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const page = await listAuditLogs({
          limit: PAGE_SIZE,
          offset,
          action: filters.action || undefined,
          object_type: filters.objectType || undefined,
          date_from: filters.dateFrom ? new Date(filters.dateFrom).toISOString() : undefined,
        });
        if (!active) return;
        setLogs(page.items);
        setTotal(page.total);
        setError(null);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load audit logs.");
      }
    })();
    return () => {
      active = false;
    };
  }, [offset, filters]);

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    setOffset(0);
    setFilters({ action, objectType, dateFrom });
  }

  function clearFilters() {
    setAction("");
    setObjectType("");
    setDateFrom("");
    setOffset(0);
    setFilters({ action: "", objectType: "", dateFrom: "" });
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit Log</h1>
        <p className="text-sm text-muted-foreground">
          Append-only trail of privileged actions across your institution (docs/14).
        </p>
      </div>

      <Card>
        <CardContent className="p-4">
          <form onSubmit={applyFilters} className="grid gap-3 sm:grid-cols-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-action">Action</Label>
              <Input
                id="f-action"
                placeholder="e.g. user.create"
                value={action}
                onChange={(e) => setAction(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-object">Object type</Label>
              <Input
                id="f-object"
                placeholder="e.g. user"
                value={objectType}
                onChange={(e) => setObjectType(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-date">From date</Label>
              <Input
                id="f-date"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button type="submit" variant="outline">
                Apply
              </Button>
              <Button type="button" variant="ghost" onClick={clearFilters}>
                Clear
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent className="p-0">
          {!logs ? (
            <div className="p-4">
              <Skeleton className="h-48 w-full" />
            </div>
          ) : logs.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">No audit entries match.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Object</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((l) => (
                  <TableRow key={l.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {fmt(l.created_at)}
                    </TableCell>
                    <TableCell>{l.actor_email ?? "system"}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{l.action}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {l.object_type ? (
                        <span>
                          {l.object_type}
                          {l.object_id ? ` · ${l.object_id.slice(0, 8)}` : ""}
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {total === 0
            ? "0 entries"
            : `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}`}
        </span>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
          >
            Previous
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
