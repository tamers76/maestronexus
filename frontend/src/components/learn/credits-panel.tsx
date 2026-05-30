"use client";

import { Coins } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { type Credit, CREDIT_STATUS_META, listCredits } from "@/lib/blueprint";

/** Learner-facing Mastery Credit ledger for one enrollment. */
export function CreditsPanel({ enrollmentId }: { enrollmentId: string }) {
  const [credits, setCredits] = useState<Credit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const rows = await listCredits(enrollmentId);
        if (active) setCredits(rows);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load credits.");
      }
    })();
    return () => {
      active = false;
    };
  }, [enrollmentId]);

  const total = (credits ?? [])
    .filter((c) => c.status === "approved" || c.status === "redeemed")
    .reduce((sum, c) => sum + c.amount, 0);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Coins className="size-4 text-muted-foreground" />
          <div>
            <CardTitle className="text-base">Mastery Credits</CardTitle>
            <CardDescription>
              {credits === null
                ? "Loading…"
                : `${total} approved credit(s) earned across ${credits.length} entr${credits.length === 1 ? "y" : "ies"}.`}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {error && <p className="text-sm text-destructive">{error}</p>}
        {credits && credits.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
            No Mastery Credits yet. Earn them through advanced challenges and
            contribution-ready work.
          </p>
        ) : (
          credits?.map((c) => (
            <div
              key={c.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{c.amount} credit(s)</span>
                  <Badge variant="outline">{c.source_type}</Badge>
                  <Badge variant={CREDIT_STATUS_META[c.status]?.variant ?? "outline"}>
                    {CREDIT_STATUS_META[c.status]?.label ?? c.status}
                  </Badge>
                </div>
                {c.rationale && (
                  <p className="mt-0.5 text-xs text-muted-foreground">{c.rationale}</p>
                )}
                {c.redeemed_for && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Redeemed for: {c.redeemed_for}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
