"use client";

import { Loader2, MessageCircle, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ReadinessStateBadge } from "@/components/learn/readiness-state-badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import {
  type NodeEvidence,
  type ReadinessState,
  listNodeEvidence,
  submitNodeEvidence,
} from "@/lib/blueprint";

const READINESS_OPTIONS: { value: ReadinessState; label: string }[] = [
  { value: "not_ready", label: "Not ready" },
  { value: "partially_ready", label: "Partially ready" },
  { value: "ready", label: "Ready" },
  { value: "advanced", label: "Advanced" },
];

/**
 * Per-node evidence task: the learner records what they did, optionally
 * self-assesses readiness, and Maestro returns a readiness state + an AI
 * Companion message. Replaces the old "mark complete" click for the Blueprint
 * evidence/readiness model.
 */
export function NodeEvidencePanel({
  enrollmentId,
  nodeId,
  onReadiness,
}: {
  enrollmentId: string;
  nodeId: string;
  onReadiness?: () => void;
}) {
  const [history, setHistory] = useState<NodeEvidence[]>([]);
  const [notes, setNotes] = useState("");
  const [selfReadiness, setSelfReadiness] = useState<ReadinessState | "">("");
  const [companion, setCompanion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const reload = useCallback(async () => {
    const rows = await listNodeEvidence(enrollmentId, nodeId);
    setHistory(rows);
    const latest = rows[rows.length - 1];
    if (latest?.ai_companion_message) setCompanion(latest.ai_companion_message);
  }, [enrollmentId, nodeId]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const rows = await listNodeEvidence(enrollmentId, nodeId);
        if (!active) return;
        setHistory(rows);
        const latest = rows[rows.length - 1];
        if (latest?.ai_companion_message) setCompanion(latest.ai_companion_message);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load evidence.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [enrollmentId, nodeId]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitNodeEvidence(enrollmentId, nodeId, {
        evidence: { notes: notes.trim() },
        readiness_state: selfReadiness || null,
      });
      setNotes("");
      setSelfReadiness("");
      setCompanion(result.ai_companion_message);
      await reload();
      onReadiness?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit evidence.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 border-t border-border bg-muted/20 p-3">
      {companion && (
        <div className="flex gap-2 rounded-lg border border-primary/30 bg-primary/5 p-2.5 text-xs">
          <MessageCircle className="mt-0.5 size-3.5 shrink-0 text-primary" />
          <p className="leading-snug">
            <span className="font-medium">AI Companion:</span> {companion}
          </p>
        </div>
      )}

      {!loading && history.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">Evidence log</Label>
          {history.map((ev) => (
            <div
              key={ev.id}
              className="flex items-center justify-between gap-2 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs"
            >
              <span className="min-w-0 truncate text-muted-foreground">
                {typeof ev.evidence?.notes === "string" && ev.evidence.notes
                  ? (ev.evidence.notes as string)
                  : "Evidence submitted"}
              </span>
              <ReadinessStateBadge state={ev.readiness_state} />
            </div>
          ))}
        </div>
      )}

      <form onSubmit={onSubmit} className="flex flex-col gap-2">
        <div className="flex flex-col gap-1">
          <Label htmlFor={`ev-${nodeId}`} className="text-xs">
            What did you do / learn here?
          </Label>
          <Textarea
            id={`ev-${nodeId}`}
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Describe your work, reasoning, or evidence of mastery…"
            className="text-xs"
            required
          />
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor={`sr-${nodeId}`} className="text-xs">
              Self-assessed readiness
            </Label>
            <select
              id={`sr-${nodeId}`}
              value={selfReadiness}
              onChange={(e) => setSelfReadiness(e.target.value as ReadinessState | "")}
              className="h-8 rounded-lg border border-border bg-background px-2 text-xs"
            >
              <option value="">Let Maestro decide</option>
              {READINESS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" size="sm" disabled={submitting || !notes.trim()}>
            {submitting ? <Loader2 className="animate-spin" /> : <Send />}
            Submit evidence
          </Button>
        </div>
      </form>

      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
