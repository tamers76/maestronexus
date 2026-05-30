"use client";

import { AuditLogView } from "@/components/admin/audit-log-view";
import { PermissionGate } from "@/components/admin/permission-gate";

export default function AuditPage() {
  return (
    <PermissionGate permission="audit.read">
      <AuditLogView />
    </PermissionGate>
  );
}
