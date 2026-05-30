"use client";

import { useEffect, useState } from "react";

import { Modal } from "@/components/admin/modal";
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
import {
  type AdminUser,
  assignRole,
  createUser,
  listRoles,
  listUsers,
  type Role,
  unassignRole,
  updateUserStatus,
} from "@/lib/iam";

const PAGE_SIZE = 20;

function statusVariant(status: string): "success" | "warning" | "secondary" {
  if (status === "active") return "success";
  if (status === "suspended") return "warning";
  return "secondary";
}

export function UsersManager() {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<AdminUser | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const page = await listUsers({ limit: PAGE_SIZE, offset, search: searchTerm });
        if (!active) return;
        setUsers(page.items);
        setTotal(page.total);
        setError(null);
      } catch (err) {
        if (active) setError(err instanceof ApiError ? err.message : "Failed to load users.");
      }
    })();
    return () => {
      active = false;
    };
  }, [offset, searchTerm, refreshKey]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const r = await listRoles();
        if (active) setRoles(r);
      } catch {
        /* roles are best-effort for the pickers */
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function reload() {
    setRefreshKey((k) => k + 1);
  }

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setOffset(0);
    setSearchTerm(search);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Users &amp; Roles</h1>
          <p className="text-sm text-muted-foreground">
            Create users, manage status, and assign roles (tenant-scoped).
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>New user</Button>
      </div>

      <form onSubmit={onSearchSubmit} className="flex gap-2">
        <Input
          placeholder="Search by name or email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Button type="submit" variant="outline">
          Search
        </Button>
      </form>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent className="p-0">
          {!users ? (
            <div className="p-4">
              <Skeleton className="h-48 w-full" />
            </div>
          ) : users.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">No users found.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Roles</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">
                      {u.display_name}
                      {u.is_superuser && (
                        <Badge variant="outline" className="ml-2">
                          super
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{u.email}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(u.status)}>{u.status}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {u.roles.length === 0 ? (
                          <span className="text-xs text-muted-foreground">—</span>
                        ) : (
                          u.roles.map((r) => (
                            <Badge key={r} variant="secondary">
                              {r}
                            </Badge>
                          ))
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="xs" variant="outline" onClick={() => setEditUser(u)}>
                        Manage
                      </Button>
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
            ? "0 users"
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

      {createOpen && (
        <CreateUserModal
          roles={roles}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            setOffset(0);
            reload();
          }}
        />
      )}

      {editUser && (
        <ManageUserModal
          user={editUser}
          roles={roles}
          onClose={() => setEditUser(null)}
          onChanged={(updated) => {
            setEditUser(updated);
            reload();
          }}
        />
      )}
    </div>
  );
}

// ── Create user ───────────────────────────────────────────────────────────────

function CreateUserModal({
  roles,
  onClose,
  onCreated,
}: {
  roles: Role[];
  onClose: () => void;
  onCreated: (u: AdminUser) => void;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleRole(key: string) {
    setSelectedRoles((prev) =>
      prev.includes(key) ? prev.filter((r) => r !== key) : [...prev, key],
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const u = await createUser({
        email,
        display_name: displayName,
        password,
        role_keys: selectedRoles,
      });
      onCreated(u);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create user.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Create user"
      description="The user is added to your institution and can sign in with the password you set."
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="cu-name">Display name</Label>
          <Input
            id="cu-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="cu-email">Email</Label>
          <Input
            id="cu-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="cu-password">Password</Label>
          <Input
            id="cu-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          <p className="text-xs text-muted-foreground">At least 8 characters.</p>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Roles</Label>
          <div className="flex flex-wrap gap-2">
            {roles.map((r) => (
              <button
                type="button"
                key={r.key}
                onClick={() => toggleRole(r.key)}
                className={
                  selectedRoles.includes(r.key)
                    ? "rounded-md border border-primary bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
                    : "rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted"
                }
              >
                {r.name}
              </button>
            ))}
          </div>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create user"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// ── Manage roles + status ───────────────────────────────────────────────────

function ManageUserModal({
  user,
  roles,
  onClose,
  onChanged,
}: {
  user: AdminUser | null;
  roles: Role[];
  onClose: () => void;
  onChanged: (u: AdminUser) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  async function run(fn: () => Promise<AdminUser>) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await fn());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Update failed.");
    } finally {
      setBusy(false);
    }
  }

  const nextStatus = user.status === "active" ? "suspended" : "active";

  return (
    <Modal
      open={user !== null}
      onClose={onClose}
      title={user.display_name}
      description={user.email}
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between rounded-lg border border-border p-3">
          <div>
            <p className="text-sm font-medium">Account status</p>
            <p className="text-xs text-muted-foreground">
              Currently <span className="font-medium">{user.status}</span>
            </p>
          </div>
          <Button
            size="sm"
            variant={nextStatus === "suspended" ? "destructive" : "default"}
            disabled={busy || user.is_superuser}
            onClick={() => run(() => updateUserStatus(user.id, nextStatus))}
          >
            {nextStatus === "suspended" ? "Suspend" : "Reactivate"}
          </Button>
        </div>

        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">Roles</p>
          <div className="flex flex-col gap-2">
            {roles.map((r) => {
              const has = user.roles.includes(r.key);
              return (
                <div
                  key={r.key}
                  className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{r.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {r.permissions.length} permissions
                    </p>
                  </div>
                  <Button
                    size="xs"
                    variant={has ? "destructive" : "outline"}
                    disabled={busy}
                    onClick={() =>
                      run(() =>
                        has ? unassignRole(user.id, r.key) : assignRole(user.id, r.key),
                      )
                    }
                  >
                    {has ? "Remove" : "Assign"}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </Modal>
  );
}
