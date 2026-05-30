/**
 * Typed IAM admin client: users, roles, the permission catalog, and audit logs.
 *
 * Mirrors the backend `/iam` endpoints (docs/02, docs/14). All calls are
 * tenant-scoped server-side; the frontend only needs to gate on permissions
 * (`user.manage`, `audit.read`).
 */

import { apiFetch } from "@/lib/api";

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminUser = {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  status: string;
  is_superuser: boolean;
  roles: string[];
  created_at: string;
};

export type Role = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  permissions: string[];
};

export type Permission = {
  key: string;
  description: string | null;
};

export type AuditLog = {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  object_type: string | null;
  object_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type CreateUserInput = {
  email: string;
  display_name: string;
  password: string;
  status?: string;
  role_keys?: string[];
};

function query(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// ── Users ────────────────────────────────────────────────────────────────────

export function listUsers(opts: {
  limit?: number;
  offset?: number;
  search?: string;
} = {}): Promise<Page<AdminUser>> {
  return apiFetch<Page<AdminUser>>(
    `/iam/users${query({ limit: opts.limit, offset: opts.offset, search: opts.search })}`,
  );
}

export function getUser(id: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/iam/users/${id}`);
}

export function createUser(input: CreateUserInput): Promise<AdminUser> {
  return apiFetch<AdminUser>("/iam/users", { method: "POST", json: input });
}

export function updateUserStatus(id: string, status: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/iam/users/${id}/status`, {
    method: "PATCH",
    json: { status },
  });
}

export function assignRole(userId: string, roleKey: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/iam/users/${userId}/roles`, {
    method: "POST",
    json: { role_key: roleKey },
  });
}

export function unassignRole(userId: string, roleKey: string): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/iam/users/${userId}/roles/${roleKey}`, {
    method: "DELETE",
  });
}

// ── Roles & permissions ───────────────────────────────────────────────────────

export function listRoles(): Promise<Role[]> {
  return apiFetch<Role[]>("/iam/roles");
}

export function listPermissions(): Promise<Permission[]> {
  return apiFetch<Permission[]>("/iam/permissions");
}

// ── Audit log ──────────────────────────────────────────────────────────────────

export function listAuditLogs(opts: {
  limit?: number;
  offset?: number;
  action?: string;
  object_type?: string;
  date_from?: string;
  date_to?: string;
} = {}): Promise<Page<AuditLog>> {
  return apiFetch<Page<AuditLog>>(`/iam/audit-logs${query(opts)}`);
}
