import Link from "next/link";

import { HealthStatus } from "@/components/health-status";
import { buttonVariants } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col items-center gap-10 text-center">
        <div className="flex flex-col items-center gap-3">
          <span className="rounded-full border border-zinc-200 px-3 py-1 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
            maestronexus
          </span>
          <h1 className="text-3xl font-semibold tracking-tight text-black dark:text-zinc-50 sm:text-4xl">
            The-Code Adaptive LMS
          </h1>
          <p className="max-w-md text-base leading-7 text-zinc-600 dark:text-zinc-400">
            Learning should not be a linear course. Learning should be an
            adaptive journey. This is the local development shell — backend,
            frontend, and services wired together.
          </p>
        </div>

        <Link href="/login" className={buttonVariants({ size: "lg" })}>
          Sign in
        </Link>

        <HealthStatus />

        <p className="text-xs text-zinc-400">
          API docs:{" "}
          <a
            className="underline underline-offset-4 hover:text-zinc-600 dark:hover:text-zinc-300"
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
          >
            localhost:8000/docs
          </a>
        </p>
      </main>
    </div>
  );
}
