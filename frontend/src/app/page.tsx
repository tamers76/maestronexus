import Link from "next/link";
import { GraduationCap, Sparkles } from "lucide-react";

import { HealthStatus } from "@/components/health-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { buttonVariants } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8011";
const DOCS_URL = `${API_BASE}/docs`;
const DOCS_LABEL = DOCS_URL.replace(/^https?:\/\//, "");

export default function Home() {
  return (
    <div className="relative flex flex-1 items-center justify-center overflow-hidden px-6 py-16">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="dark-grid absolute inset-0 opacity-30" />
        <div className="absolute -left-40 top-0 h-96 w-96 rounded-full bg-blue-600/20 blur-[120px]" />
        <div className="absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-purple-600/20 blur-[120px]" />
      </div>

      <div className="absolute right-6 top-6">
        <ThemeToggle />
      </div>

      <main className="flex w-full max-w-2xl flex-col items-center gap-10 text-center">
        <div className="flex flex-col items-center gap-5">
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 via-purple-500 to-indigo-500 text-white shadow-xl shadow-primary/30 glow-effect">
            <GraduationCap className="size-8" />
            <Sparkles className="absolute -right-1.5 -top-1.5 size-5 text-amber-300" />
          </div>
          <span className="rounded-full border border-border bg-card/60 px-4 py-1.5 text-sm font-medium uppercase tracking-wider text-muted-foreground backdrop-blur">
            Maestro Nexus
          </span>
          <h1 className="font-display text-4xl tracking-tight sm:text-5xl">
            <span className="gradient-text">Curriculum Intelligence</span>
          </h1>
          <p className="max-w-lg text-base leading-7 text-muted-foreground">
            Turn a course syllabus into a node-based adaptive learning curriculum.
            Learning should not be a linear course — it should be an adaptive
            journey.
          </p>
        </div>

        <Link
          href="/login"
          className={buttonVariants({ size: "lg", className: "shadow-lg shadow-primary/20" })}
        >
          <Sparkles className="size-4" />
          Sign in
        </Link>

        <HealthStatus />

        <p className="text-xs text-muted-foreground">
          API docs:{" "}
          <a
            className="underline underline-offset-4 transition-colors hover:text-primary"
            href={DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
          >
            {DOCS_LABEL}
          </a>
        </p>
      </main>
    </div>
  );
}
