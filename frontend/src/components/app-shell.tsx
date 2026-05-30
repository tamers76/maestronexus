"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as Icons from "lucide-react";
import { GraduationCap, Sparkles } from "lucide-react";
import { useState } from "react";
import type { ComponentType } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { NAV_SECTIONS } from "@/lib/nav";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

type IconProps = { className?: string };

function kebabToPascal(name: string): string {
  return name
    .split("-")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join("");
}

function Icon({ name, className }: { name: string; className?: string }) {
  const registry = Icons as unknown as Record<string, ComponentType<IconProps>>;
  const Cmp = registry[kebabToPascal(name)] ?? registry["Circle"];
  return Cmp ? <Cmp className={className} /> : null;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, signOut, hasPermission } = useAuth();
  const { theme } = useTheme();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const sections = NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((i) => !i.permission || hasPermission(i.permission)),
  })).filter((s) => s.items.length > 0);

  const isDark = theme === "dark";

  return (
    <div className="relative flex min-h-screen w-full">
      {/* Ambient glow + grid for dark mode */}
      {isDark && (
        <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
          <div className="dark-grid absolute inset-0 opacity-40" />
          <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-blue-600/20 blur-[120px]" />
          <div className="absolute right-0 top-1/3 h-96 w-96 rounded-full bg-purple-600/20 blur-[120px]" />
          <div className="absolute bottom-0 left-1/3 h-96 w-96 rounded-full bg-indigo-600/10 blur-[120px]" />
        </div>
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 shrink-0 border-r border-sidebar-border bg-sidebar/80 text-sidebar-foreground backdrop-blur-xl transition-transform md:static md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-4">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-indigo-500 text-white shadow-lg shadow-primary/30">
            <GraduationCap className="size-5" />
            <Sparkles className="absolute -right-1 -top-1 size-3 text-amber-300" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-display text-base tracking-tight gradient-text">
              Curriculum Intelligence
            </span>
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Adaptive Learning System
            </span>
          </div>
        </div>
        <nav className="flex flex-col gap-6 overflow-y-auto px-3 py-4">
          {sections.map((section) => (
            <div key={section.title}>
              <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {section.title}
              </p>
              <ul className="space-y-0.5">
                {section.items.map((item) => {
                  const active =
                    pathname === item.href || pathname.startsWith(item.href + "/");
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-all",
                          active
                            ? "bg-gradient-to-r from-primary/15 to-accent/10 text-foreground font-medium shadow-sm ring-1 ring-primary/20"
                            : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                        )}
                      >
                        <Icon
                          name={item.icon}
                          className={cn(
                            "size-4 transition-colors",
                            active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
                          )}
                        />
                        {item.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-background/70 px-4 backdrop-blur-xl md:px-8">
          <Button
            variant="ghost"
            size="icon-sm"
            className="md:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-label="Toggle navigation"
          >
            <Icon name="menu" className="size-4" />
          </Button>
          <div className="ml-auto flex items-center gap-3">
            <ThemeToggle />
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium leading-tight">{user?.display_name}</p>
              <p className="text-xs text-muted-foreground leading-tight">{user?.email}</p>
            </div>
            <Button variant="outline" size="sm" onClick={signOut}>
              <Icon name="log-out" className="size-3.5" />
              Sign out
            </Button>
          </div>
        </header>
        <main className="flex-1 px-4 py-6 md:px-8">{children}</main>
        <footer className="border-t border-border px-4 py-4 md:px-8">
          <div className="flex flex-col items-center justify-between gap-1 text-center text-xs text-muted-foreground sm:flex-row sm:text-left">
            <span>Adaptive Curriculum Intelligence System</span>
            <span>
              Developed by{" "}
              <span className="gradient-text font-medium">the-Code.ai Labs</span>
            </span>
          </div>
        </footer>
      </div>

      {open && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}
    </div>
  );
}
