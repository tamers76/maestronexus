"use client";

import { Coins, Inbox, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { SubmissionGradePanel } from "@/components/faculty/submission-grade-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Credit,
  type Submission,
  CREDIT_STATUS_META,
  SUBMISSION_STATUS_META,
  approveCredit,
  awardCredit,
  listCredits,
  listSubmissions,
  redeemCredit,
} from "@/lib/blueprint";

/**
 * Faculty view of one enrollment's assessment submissions (grade/evaluate/revise)
 * plus its Mastery Credit ledger (award, approve, redeem). Rendered under the
 * class roster's learner-progress view.
 */
export function EnrollmentSubmissions({ enrollmentId }: { enrollmentId: string }) {
  const { hasPermission } = useAuth();
  const canAward = hasPermission("project.grade");
  const canApprove = hasPermission("stage.review");

  const [submissions, setSubmissions] = useState<Submission[] | null>(null);
  const [credits, setCredits] = useState<Credit[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [amount, setAmount] = useState("1");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const loadCredits = useCallback(async () => {
    try {
      const rows = await listCredits(enrollmentId);
      setCredits(rows);
    } catch {
      setCredits([]);
    }
  }, [enrollmentId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const rows = await listSubmissions({ enrollment_id: enrollmentId });
        if (active) setSubmissions(rows);
      } catch (err) {
        if (!active) return;
        if (err instanceof ApiError && err.status === 403) setSubmissions([]);
        else
          setError(
            err instanceof ApiError ? err.message : "Failed to load submissions.",
          );
      }
      const credits = await listCredits(enrollmentId).catch(() => []);
      if (active) setCredits(credits);
    })();
    return () => {
      active = false;
    };
  }, [enrollmentId]);

  const wrap = useCallback(async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed.");
    } finally {
      setBusy(null);
    }
  }, []);

  const onAward = () =>
    wrap("award", async () => {
      await awardCredit(enrollmentId, {
        source_type: "other",
        amount: Number(amount) || 0,
        rationale: rationale.trim() || null,
      });
      setRationale("");
      await loadCredits();
    });

  const onApprove = (id: string) =>
    wrap(`approve-${id}`, async () => {
      await approveCredit(id);
      await loadCredits();
    });

  const onRedeem = (id: string) =>
    wrap(`redeem-${id}`, async () => {
      await redeemCredit(id, "faculty review");
      await loadCredits();
    });

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Inbox className="size-4 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Assessment submissions</CardTitle>
              <CardDescription>
                {submissions === null
                  ? "Loading…"
                  : `${submissions.length} submission(s) — select one to evaluate and grade.`}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {error && <p className="text-sm text-destructive">{error}</p>}
          {submissions && submissions.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
              No submissions for this learner yet.
            </p>
          ) : (
            submissions?.map((s) => {
              const meta = SUBMISSION_STATUS_META[s.status];
              const open = selected === s.id;
              return (
                <div key={s.id} className="flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={() => setSelected(open ? null : s.id)}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-left text-sm"
                  >
                    <span className="min-w-0 truncate font-mono text-xs">
                      {s.assessment_id.slice(0, 8)} · v{s.version}
                    </span>
                    <Badge variant={meta?.variant ?? "outline"}>{meta?.label ?? s.status}</Badge>
                  </button>
                  {open && (
                    <SubmissionGradePanel
                      submission={s}
                      onChanged={(updated) =>
                        setSubmissions((prev) =>
                          prev ? prev.map((x) => (x.id === updated.id ? updated : x)) : prev,
                        )
                      }
                    />
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Coins className="size-4 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Mastery Credits</CardTitle>
              <CardDescription>
                Award, approve, and redeem Mastery Credits for this learner.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {credits && credits.length > 0 &&
            credits.map((c) => {
              const meta = CREDIT_STATUS_META[c.status];
              return (
                <div
                  key={c.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{c.amount}</span>
                      <Badge variant="outline">{c.source_type}</Badge>
                      <Badge variant={meta?.variant ?? "outline"}>{meta?.label ?? c.status}</Badge>
                    </div>
                    {c.rationale && (
                      <p className="mt-0.5 text-xs text-muted-foreground">{c.rationale}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    {canApprove && c.status === "recommended" && (
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => onApprove(c.id)}
                        disabled={busy === `approve-${c.id}`}
                      >
                        Approve
                      </Button>
                    )}
                    {canAward && c.status === "approved" && (
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => onRedeem(c.id)}
                        disabled={busy === `redeem-${c.id}`}
                      >
                        Redeem
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}

          {canAward && (
            <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
              <Input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="h-8 w-20 text-xs"
                aria-label="Credit amount"
              />
              <Input
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Rationale (e.g. contribution-ready work)…"
                className="h-8 flex-1 text-xs"
              />
              <Button size="sm" onClick={onAward} disabled={busy === "award"}>
                {busy === "award" ? <Loader2 className="animate-spin" /> : <Coins />}
                Award credit
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
