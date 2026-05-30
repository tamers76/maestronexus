"use client";

import { InstitutionDashboardView } from "@/components/admin/institution-dashboard";
import { PermissionGate } from "@/components/admin/permission-gate";

export default function AdminDashboardPage() {
  return (
    <PermissionGate permission="dashboard.view_institution">
      <InstitutionDashboardView />
    </PermissionGate>
  );
}
