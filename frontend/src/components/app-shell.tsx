"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as Icons from "lucide-react";
import { useState } from "react";
import type { ComponentType } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { NAV_SECTIONS } from "@/lib/nav";
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
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const sections = NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((i) => !i.permission || hasPermission(i.permission)),
  })).filter((s) => s.items.length > 0);

  return (
    <div className="flex min-h-screen w-full">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform md:static md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold">
            M
          </div>
          <span className="text-sm font-semibold tracking-tight">maestronexus</span>
        </div>
        <nav className="flex flex-col gap-6 overflow-y-auto px-3 py-4">
          {sections.map((section) => (
            <div key={section.title}>
              <p className="px-2 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
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
                          "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition-colors",
                          active
                            ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                            : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                        )}
                      >
                        <Icon name={item.icon} className="size-4" />
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
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
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
            <div className="text-right">
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
