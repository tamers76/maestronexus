"use client";

import { PermissionGate } from "@/components/admin/permission-gate";
import { UsersManager } from "@/components/admin/users-manager";

export default function UsersPage() {
  return (
    <PermissionGate permission="user.manage">
      <UsersManager />
    </PermissionGate>
  );
}
