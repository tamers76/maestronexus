"use client";

import {
  Award,
  CheckCircle2,
  ClipboardCheck,
  FileUp,
  Loader2,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import {
  type Contribution,
  type ContextProfile,
  type ContributionAssessment,
  type Evaluation,
  type ReadinessGateResult,
  type Submission,
  type VisibilityLevel,
  GATE_OUTCOME_META,
  SUBMISSION_STATUS_META,
  VERIFICATION_META,
  checkReadiness,
  createSubmission,
  getEvaluation,
  listEnrollmentContributions,
  listSubmissions,
  prepareContribution,
  submitContextProfile,
  submitSubmission,
  updateSubmission,
} from "@/lib/blueprint";

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function StatusBadge({ status }: { status: string }) {
  const meta = SUBMISSION_STATUS_META[status];
  return <Badge variant={meta?.variant ?? "outline"}>{meta?.label ?? status}</Badge>;
}

/**
 * The full learner-side lifecycle for one contribution assessment: context
 * profile → readiness gate → formal submission → feedback/grade → contribution
 * preparation. Operates on the learner's latest submission for the assessment.
 */
export function AssessmentWorkflow({
  assessment,
  enrollmentId,
}: {
  assessment: ContributionAssessment;
  enrollmentId: string;
}) {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [contextProfile, setContextProfile] = useState<ContextProfile | null>(null);
  const [readiness, setReadiness] = useState<ReadinessGateResult | null>(null);
  const [contributions, setContributions] = useState<Contribution[]>([]);

  const [contextText, setContextText] = useState("");
  const [packageText, setPackageText] = useState("");
  const [aiDisclosure, setAiDisclosure] = useState("");

  // Contribution prep form.
  const [contribTitle, setContribTitle] = useState("");
  const [contribSummary, setContribSummary] = useState("");
  const [contribFormat, setContribFormat] = useState("");
  const [contribVisibility, setContribVisibility] = useState<VisibilityLevel>("internal");
  const [contribConsent, setContribConsent] = useState(false);
  const [contribAnon, setContribAnon] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const latest = submissions[submissions.length - 1] ?? null;

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const subs = await listSubmissions({
          assessment_id: assessment.id,
          enrollment_id: enrollmentId,
        });
        const last = subs[subs.length - 1] ?? null;
        const evalRow = last ? await getEvaluation(last.id).catch(() => null) : null;
        const contribs = await listEnrollmentContributions(enrollmentId).catch(
          () => [] as Contribution[],
        );
        if (!active) return;
        setSubmissions(subs);
        if (last) {
          setPackageText(asText(last.package?.response));
          setAiDisclosure(asText(last.package?.ai_use_disclosure));
        }
        setEvaluation(evalRow);
        setContributions(contribs.filter((c) => !last || c.submission_id === last.id));
        setError(null);
      } catch (err) {
        if (active)
          setError(err instanceof ApiError ? err.message : "Failed to load assessment.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [assessment.id, enrollmentId]);

  const wrap = useCallback(
    async (key: string, fn: () => Promise<void>) => {
      setBusy(key);
      setError(null);
      try {
        await fn();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Action failed.");
      } finally {
        setBusy(null);
      }
    },
    [],
  );

  const onSubmitContext = () =>
    wrap("context", async () => {
      const profile = await submitContextProfile(assessment.id, {
        enrollment_id: enrollmentId,
        profile: { description: contextText.trim() },
      });
      setContextProfile(profile);
    });

  const onCheckReadiness = () =>
    wrap("readiness", async () => {
      const result = await checkReadiness(assessment.id, enrollmentId);
      setReadiness(result);
    });

  const buildPackage = () => ({
    response: packageText.trim(),
    ai_use_disclosure: aiDisclosure.trim(),
  });

  const onSaveDraft = () =>
    wrap("draft", async () => {
      if (latest && (latest.status === "draft" || latest.status === "revision_requested")) {
        const updated = await updateSubmission(latest.id, buildPackage());
        setSubmissions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      } else {
        const created = await createSubmission(assessment.id, {
          enrollment_id: enrollmentId,
          package: buildPackage(),
          submit: false,
        });
        setSubmissions((prev) => [...prev, created]);
      }
    });

  const onSubmitFinal = () =>
    wrap("submit", async () => {
      let target = latest;
      if (!target || target.status === "graded") {
        target = await createSubmission(assessment.id, {
          enrollment_id: enrollmentId,
          package: buildPackage(),
          submit: true,
        });
        setSubmissions((prev) => [...prev, target as Submission]);
        return;
      }
      // Persist edits then finalize.
      if (target.status === "draft" || target.status === "revision_requested") {
        await updateSubmission(target.id, buildPackage());
      }
      const finalized = await submitSubmission(target.id);
      setSubmissions((prev) => prev.map((s) => (s.id === finalized.id ? finalized : s)));
    });

  const onPrepareContribution = () =>
    wrap("contribution", async () => {
      if (!latest) return;
      const created = await prepareContribution(latest.id, {
        title: contribTitle.trim() || assessment.title,
        summary: contribSummary.trim() || null,
        format: contribFormat.trim() || null,
        body: { response: packageText.trim() },
        visibility_level: contribVisibility,
        consent: contribConsent,
        anonymized: contribAnon,
      });
      setContributions((prev) => [...prev, created]);
      setContribTitle("");
      setContribSummary("");
    });

  const isGraded = latest?.status === "graded";
  const isEditable =
    !latest || latest.status === "draft" || latest.status === "revision_requested" || isGraded;

  if (loading) {
    return (
      <div className="rounded-lg border border-border p-3 text-sm text-muted-foreground">
        Loading assessment workflow…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 border-t border-border p-4">
      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* 1 — Context profile */}
      <section className="flex flex-col gap-2">
        <h4 className="flex items-center gap-1.5 text-sm font-medium">
          <Sparkles className="size-4 text-primary" /> 1. Personalize your context
        </h4>
        <p className="text-xs text-muted-foreground">
          The academic core is fixed; tailor the context to your situation. A faculty
          member reviews and approves it.
        </p>
        <Textarea
          rows={2}
          value={contextText}
          onChange={(e) => setContextText(e.target.value)}
          placeholder="Describe the real context you'll apply this work to…"
          className="text-sm"
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={onSubmitContext}
            disabled={busy === "context" || !contextText.trim()}
          >
            {busy === "context" ? <Loader2 className="animate-spin" /> : <ClipboardCheck />}
            Submit context profile
          </Button>
          {contextProfile && (
            <Badge variant={contextProfile.status === "approved" ? "success" : "warning"}>
              {contextProfile.status}
            </Badge>
          )}
        </div>
      </section>

      {/* 2 — Readiness gate */}
      <section className="flex flex-col gap-2">
        <h4 className="flex items-center gap-1.5 text-sm font-medium">
          <ShieldCheck className="size-4 text-primary" /> 2. Readiness gate
        </h4>
        <div>
          <Button
            size="sm"
            variant="outline"
            onClick={onCheckReadiness}
            disabled={busy === "readiness"}
          >
            {busy === "readiness" ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
            Check readiness
          </Button>
        </div>
        {readiness && (
          <div className="rounded-lg border border-border p-3 text-sm">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant={GATE_OUTCOME_META[readiness.outcome]?.variant ?? "outline"}>
                {GATE_OUTCOME_META[readiness.outcome]?.label ?? readiness.outcome}
              </Badge>
              {readiness.context_profile_approved && (
                <Badge variant="success">Context approved</Badge>
              )}
            </div>
            <ul className="flex flex-col gap-1">
              {readiness.checks.map((c, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs">
                  {c.passed ? (
                    <CheckCircle2 className="mt-0.5 size-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="mt-0.5 size-3.5 text-destructive" />
                  )}
                  <span>
                    <span className="font-medium">{c.check}</span>
                    {c.detail ? ` — ${c.detail}` : ""}
                  </span>
                </li>
              ))}
            </ul>
            {readiness.missing_node_keys.length > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Missing nodes: {readiness.missing_node_keys.join(", ")}
              </p>
            )}
          </div>
        )}
      </section>

      {/* 3 — Submission */}
      <section className="flex flex-col gap-2">
        <h4 className="flex items-center gap-1.5 text-sm font-medium">
          <FileUp className="size-4 text-primary" /> 3. Formal submission
          {latest && <StatusBadge status={latest.status} />}
        </h4>
        {assessment.required_artifact && (
          <p className="text-xs text-muted-foreground">
            Required artifact: {assessment.required_artifact}
          </p>
        )}
        <div className="flex flex-col gap-1">
          <Label htmlFor={`pkg-${assessment.id}`} className="text-xs">
            Your work
          </Label>
          <Textarea
            id={`pkg-${assessment.id}`}
            rows={4}
            value={packageText}
            onChange={(e) => setPackageText(e.target.value)}
            placeholder="Paste or describe your contribution artifact…"
            className="text-sm"
            disabled={!isEditable}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor={`ai-${assessment.id}`} className="text-xs">
            AI-use disclosure
          </Label>
          <Textarea
            id={`ai-${assessment.id}`}
            rows={2}
            value={aiDisclosure}
            onChange={(e) => setAiDisclosure(e.target.value)}
            placeholder="How did you use AI? Which decisions were yours?"
            className="text-sm"
            disabled={!isEditable}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={onSaveDraft}
            disabled={busy === "draft" || !isEditable || !packageText.trim()}
          >
            {busy === "draft" ? <Loader2 className="animate-spin" /> : null}
            Save draft
          </Button>
          <Button
            size="sm"
            onClick={onSubmitFinal}
            disabled={busy === "submit" || !isEditable || !packageText.trim()}
          >
            {busy === "submit" ? <Loader2 className="animate-spin" /> : <FileUp />}
            Submit for evaluation
          </Button>
        </div>
      </section>

      {/* 4 — Feedback & grade */}
      {evaluation && (
        <section className="flex flex-col gap-2">
          <h4 className="flex items-center gap-1.5 text-sm font-medium">
            <ClipboardCheck className="size-4 text-primary" /> 4. Feedback &amp; grade
          </h4>
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              {evaluation.recommendation && (
                <Badge variant="secondary">{evaluation.recommendation}</Badge>
              )}
              {evaluation.finalized && typeof evaluation.grade === "number" && (
                <Badge variant="success">Grade: {evaluation.grade}</Badge>
              )}
              {evaluation.integrity_flag && (
                <Badge variant="destructive">Integrity flag</Badge>
              )}
              {evaluation.publication_potential && (
                <Badge variant="outline">{evaluation.publication_potential}</Badge>
              )}
            </div>
            {evaluation.feedback_learner && (
              <p className="text-xs leading-snug text-muted-foreground">
                {evaluation.feedback_learner}
              </p>
            )}
          </div>
          {latest?.status === "revision_requested" && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              A revision was requested — edit your work above and resubmit.
            </p>
          )}
        </section>
      )}

      {/* 5 — Contribution preparation */}
      {isGraded && (
        <section className="flex flex-col gap-2">
          <h4 className="flex items-center gap-1.5 text-sm font-medium">
            <Award className="size-4 text-primary" /> 5. Prepare a contribution
          </h4>
          {contributions.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {contributions.map((c) => (
                <div
                  key={c.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-2.5 py-1.5 text-xs"
                >
                  <span className="min-w-0 truncate font-medium">
                    {c.title ?? "Contribution"}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Badge variant="outline">{c.visibility_level}</Badge>
                    <Badge variant={VERIFICATION_META[c.verification_status]?.variant ?? "outline"}>
                      {VERIFICATION_META[c.verification_status]?.label ?? c.verification_status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Input
              value={contribTitle}
              onChange={(e) => setContribTitle(e.target.value)}
              placeholder="Contribution title"
            />
            <Input
              value={contribFormat}
              onChange={(e) => setContribFormat(e.target.value)}
              placeholder="Format (article, video, dataset…)"
            />
          </div>
          <Textarea
            rows={2}
            value={contribSummary}
            onChange={(e) => setContribSummary(e.target.value)}
            placeholder="Public-facing summary…"
            className="text-sm"
          />
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-1.5">
              <span>Visibility</span>
              <select
                value={contribVisibility}
                onChange={(e) => setContribVisibility(e.target.value as VisibilityLevel)}
                className="h-8 rounded-lg border border-border bg-background px-2"
              >
                <option value="private">Private</option>
                <option value="internal">Internal</option>
                <option value="public">Public</option>
              </select>
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={contribConsent}
                onChange={(e) => setContribConsent(e.target.checked)}
              />
              I consent to publication
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={contribAnon}
                onChange={(e) => setContribAnon(e.target.checked)}
              />
              Anonymize
            </label>
          </div>
          <div>
            <Button
              size="sm"
              onClick={onPrepareContribution}
              disabled={busy === "contribution"}
            >
              {busy === "contribution" ? <Loader2 className="animate-spin" /> : <Award />}
              Prepare contribution
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}
