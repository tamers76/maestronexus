"use client";

import { TutorChat } from "@/components/ai/tutor-chat";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/lib/auth";

export default function TutorPage() {
  const { hasPermission } = useAuth();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 py-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">AI Tutor</h1>
        <p className="text-sm text-muted-foreground">
          Get help grounded in your approved course content.
        </p>
      </div>

      {hasPermission("tutor.use") ? (
        <TutorChat />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">No tutor access</CardTitle>
            <CardDescription>
              Your account doesn&apos;t have the <code>tutor.use</code> permission. Ask an
              administrator to grant access.
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      )}
    </div>
  );
}
