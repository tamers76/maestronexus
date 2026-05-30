"use client";

import { ClassReports } from "@/components/admin/class-reports";
import { PermissionGate } from "@/components/admin/permission-gate";

export default function ReportsPage() {
  return (
    <PermissionGate permission="report.view_class">
      <ClassReports
        title="Reports"
        description="Class enrollment, node-progress completion, and attendance — scoped to your role."
      />
    </PermissionGate>
  );
}
