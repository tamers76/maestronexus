"use client";

import { PermissionGate } from "@/components/admin/permission-gate";
import { TeacherOverview } from "@/components/admin/teacher-overview";

export default function TeacherOverviewPage() {
  return (
    <PermissionGate permission="report.view_class">
      <TeacherOverview />
    </PermissionGate>
  );
}
