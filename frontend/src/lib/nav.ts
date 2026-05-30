/**
 * Navigation model for the authenticated app shell.
 *
 * Each item is gated by a permission key (docs/02). The shell filters items the
 * current user can't access. Feature modules build out the pages these point to.
 */

export type NavItem = {
  label: string;
  href: string;
  /** Required permission (omit for items every authenticated user can see). */
  permission?: string;
  /** Lucide icon name (resolved in the shell). */
  icon: string;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

export const NAV_SECTIONS: NavSection[] = [
  {
    title: "Learn",
    items: [
      { label: "My Journey", href: "/learn", permission: "node.progress", icon: "compass" },
      { label: "AI Tutor", href: "/learn/tutor", permission: "tutor.use", icon: "sparkles" },
    ],
  },
  {
    title: "Teach",
    items: [
      { label: "Overview", href: "/teacher", permission: "report.view_class", icon: "layout-dashboard" },
      { label: "Classes", href: "/teacher/classes", permission: "class.manage", icon: "users" },
      { label: "Attendance", href: "/teacher/attendance", permission: "attendance.manage", icon: "calendar-check" },
      { label: "Grading", href: "/teacher/grading", permission: "project.grade", icon: "clipboard-check" },
      { label: "Submissions", href: "/teacher/submissions", permission: "project.grade", icon: "inbox" },
      { label: "Analytics", href: "/teacher/analytics", permission: "report.view_class", icon: "bar-chart-3" },
    ],
  },
  {
    title: "Design",
    items: [
      { label: "Courses", href: "/admin/courses", permission: "course.manage", icon: "graduation-cap" },
      { label: "Maestro Studio", href: "/admin/stages", permission: "stage.run", icon: "layers" },
      { label: "Learning Graph", href: "/admin/graph", permission: "graph.manage", icon: "workflow" },
      { label: "Content", href: "/admin/content", permission: "content.author", icon: "file-text" },
    ],
  },
  {
    title: "Administer",
    items: [
      { label: "Dashboard", href: "/admin", permission: "dashboard.view_institution", icon: "layout-dashboard" },
      { label: "Users & Roles", href: "/admin/users", permission: "user.manage", icon: "shield" },
      { label: "Reports", href: "/admin/reports", permission: "report.view_class", icon: "bar-chart-3" },
      { label: "Integrations & AI", href: "/admin/settings", permission: "integration.manage", icon: "settings" },
      { label: "Audit Log", href: "/admin/audit", permission: "audit.read", icon: "scroll-text" },
    ],
  },
];
