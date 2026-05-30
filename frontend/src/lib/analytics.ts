/**
 * Typed analytics client: class reports & the institution dashboard (docs/09).
 *
 * Read-only and tenant-scoped server-side. `report.view_class` gates class
 * reports (teachers see their own classes); `dashboard.view_institution` gates
 * the institution summary.
 */

import { apiFetch } from "@/lib/api";

export type ClassSummary = {
  class_id: string;
  name: string;
  course_title: string | null;
  teacher_id: string | null;
  enrollment_count: number;
};

export type ClassReport = {
  class_id: string;
  name: string;
  course_title: string | null;
  teacher_id: string | null;
  enrollment_count: number;
  active_enrollment_count: number;
  total_nodes: number;
  completed_nodes: number;
  avg_completion_pct: number;
  attendance_records: number;
  attendance_rate: number;
};

export type RoleCount = { role: string; count: number };

export type InstitutionDashboard = {
  totals: {
    users: number;
    courses: number;
    classes: number;
    enrollments: number;
  };
  engagement: {
    active_enrollments: number;
    avg_completion_pct: number;
    attendance_rate: number;
  };
  top_classes: ClassSummary[];
  users_by_role: RoleCount[];
};

export function listReportClasses(): Promise<ClassSummary[]> {
  return apiFetch<ClassSummary[]>("/analytics/classes");
}

export function getClassReport(classId: string): Promise<ClassReport> {
  return apiFetch<ClassReport>(`/analytics/classes/${classId}/report`);
}

export function getInstitutionDashboard(): Promise<InstitutionDashboard> {
  return apiFetch<InstitutionDashboard>("/analytics/dashboard/institution");
}
