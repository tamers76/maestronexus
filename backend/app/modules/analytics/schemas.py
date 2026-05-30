"""Analytics response schemas: class reports & institution dashboard (docs/09)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class ClassSummary(BaseModel):
    """Lightweight class row for lists and dashboards."""

    class_id: uuid.UUID
    name: str
    course_title: str | None = None
    teacher_id: uuid.UUID | None = None
    enrollment_count: int


class ClassReport(BaseModel):
    """Detailed, read-only report for a single class (report.view_class)."""

    class_id: uuid.UUID
    name: str
    course_title: str | None = None
    teacher_id: uuid.UUID | None = None
    enrollment_count: int
    active_enrollment_count: int
    total_nodes: int
    completed_nodes: int
    avg_completion_pct: float
    attendance_records: int
    attendance_rate: float


class DashboardTotals(BaseModel):
    users: int
    courses: int
    classes: int
    enrollments: int


class DashboardEngagement(BaseModel):
    active_enrollments: int
    avg_completion_pct: float
    attendance_rate: float


class RoleCount(BaseModel):
    role: str
    count: int


class InstitutionDashboard(BaseModel):
    """Institution-wide summary (dashboard.view_institution)."""

    totals: DashboardTotals
    engagement: DashboardEngagement
    top_classes: list[ClassSummary]
    users_by_role: list[RoleCount]
