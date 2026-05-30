"use client";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";

/**
 * Client-side RBAC guard for admin pages. The backend is always the source of
 * truth (403s), but this gives a friendly block when a user navigates directly
 * to an out-of-scope route (docs/02).
 */
export function PermissionGate({
  permission,
  children,
}: {
  permission: string;
  children: React.ReactNode;
}) {
  const { hasPermission } = useAuth();
  if (!hasPermission(permission)) {
    return (
      <div className="mx-auto w-full max-w-2xl py-10">
        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Access restricted</CardTitle>
            <CardDescription>
              You don&apos;t have permission to view this page. Contact an administrator if
              you believe this is a mistake.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }
  return <>{children}</>;
}
