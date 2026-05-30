"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { GraduationCap, Sparkles } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { primaryRouteFor, useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { user, loading, signIn } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already signed in -> bounce to the role's primary route.
  useEffect(() => {
    if (!loading && user) router.replace(primaryRouteFor(user));
  }, [loading, user, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signIn(username, password);
      // Redirect handled by the effect once `user` populates.
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to sign in. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex flex-1 items-center justify-center overflow-hidden px-6 py-16">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="dark-grid absolute inset-0 opacity-30" />
        <div className="absolute -left-40 top-0 h-96 w-96 rounded-full bg-blue-600/20 blur-[120px]" />
        <div className="absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-purple-600/20 blur-[120px]" />
      </div>
      <div className="absolute right-6 top-6">
        <ThemeToggle />
      </div>
      <Card className="w-full max-w-sm border-border bg-card/70 shadow-2xl backdrop-blur-xl">
        <CardHeader className="items-center text-center">
          <div className="relative mb-2 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 via-purple-500 to-indigo-500 text-white shadow-lg shadow-primary/30">
            <GraduationCap className="size-7" />
            <Sparkles className="absolute -right-1.5 -top-1.5 size-4 text-amber-300" />
          </div>
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            maestronexus
          </span>
          <CardTitle className="font-display text-3xl">
            <span className="gradient-text">Curriculum Intelligence</span>
          </CardTitle>
          <CardDescription>Sign in to the Adaptive Learning System</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={submitting} className="mt-1">
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Dev users: <code className="font-mono">admin</code>,{" "}
            <code className="font-mono">designer</code>,{" "}
            <code className="font-mono">teacher</code>,{" "}
            <code className="font-mono">learner</code> · password{" "}
            <code className="font-mono">pass</code>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
