"use client";

import {
  CheckCircle2,
  ClipboardList,
  Clock,
  FileSearch,
  Loader2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StageArtifactView } from "@/components/stages/stage-artifact-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type ContributionAssessment,
  approveAssessment,
  listAssessments,
} from "@/lib/blueprint";
import { type ApprovedArtifact, getApprovedArtifact } from "@/lib/stages";

function statusVariant(status: string) {
  if (status === "approved" || status === "published") return "success" as const;
  if (status === "rejected") return "destructive" as const;
  if (status === "draft") return "secondary" as const;
  return "outline" as const;
}

/**
 * Blueprint-specific course setup: the approved intake summary, the contribution
 * assessment blueprints (review + approve), and the learning-hours / credit-hour
 * equivalency view. Mounted alongside the CLO review in the course detail.
 */
export function BlueprintCoursePanel({
  courseId,
  creditHours,
}: {
  courseId: string;
  creditHours: number | null;
}) {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("course.manage");

  const [intake, setIntake] = useState<ApprovedArtifact | null>(null);
  const [effort, setEffort] = useState<ApprovedArtifact | null>(null);
  const [assessments, setAssessments] = useState<ContributionAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [intakeArt, effortArt, list] = await Promise.all([
          getApprovedArtifact(courseId, "intake").catch(() => null),
          getApprovedArtifact(courseId, "learning_hours").catch(() => null),
          listAssessments(courseId).catch(() => [] as ContributionAssessment[]),
        ]);
        if (!active) return;
        setIntake(intakeArt);
        setEffort(effortArt);
        setAssessments(list);
        setError(null);
      } catch (err) {
        if (active)
          setError(
            err instanceof ApiError ? err.message : "Failed to load Blueprint state.",
          );
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [courseId]);

  const onApprove = useCallback(
    async (assessmentId: string) => {
      setApproving(assessmentId);
      setError(null);
      try {
        const updated = await approveAssessment(assessmentId);
        setAssessments((prev) =>
          prev.map((a) => (a.id === updated.id ? updated : a)),
        );
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not approve assessment.");
      } finally {
        setApproving(null);
      }
    },
    [],
  );

  if (!canManage) return null;

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {/* Intake summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileSearch className="size-4 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Intake summary</CardTitle>
              <CardDescription>
                Approved syllabus extraction: structure, assessments, and credit hours.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : intake?.artifact ? (
            <StageArtifactView artifact={intake.artifact} outputKind="course_contract" />
          ) : (
            <p className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
              No approved intake yet. Run the Intake stage in Maestro Studio and
              approve it to populate this summary.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Contribution assessment blueprints */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ClipboardList className="size-4 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Contribution assessments</CardTitle>
              <CardDescription>
                {loading ? "Loading…" : `${assessments.length} assessment blueprint(s)`} —
                review and approve before learners can submit.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {loading ? (
            <Skeleton className="h-20 w-full" />
          ) : assessments.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
              No contribution assessments yet. Approve the Assessment Redesign stage
              in Maestro Studio to generate blueprints.
            </p>
          ) : (
            assessments.map((a) => {
              const isOpen = expanded === a.id;
              const isApproved = a.status === "approved" || a.status === "published";
              return (
                <div key={a.id} className="rounded-lg border border-border">
                  <div className="flex flex-wrap items-center justify-between gap-2 p-3">
                    <button
                      type="button"
                      onClick={() => setExpanded(isOpen ? null : a.id)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="font-mono">
                          {a.assessment_key}
                        </Badge>
                        <span className="truncate text-sm font-medium">{a.title}</span>
                        <Badge variant={statusVariant(a.status)}>{a.status}</Badge>
                        {typeof a.weight === "number" && (
                          <Badge variant="secondary">{Math.round(a.weight * 100) / 100}% weight</Badge>
                        )}
                        {a.publication_potential && (
                          <Badge variant="outline">{a.publication_potential}</Badge>
                        )}
                      </div>
                      {a.contribution_purpose && (
                        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                          {a.contribution_purpose}
                        </p>
                      )}
                    </button>
                    {!isApproved && (
                      <Button
                        size="sm"
                        onClick={() => onApprove(a.id)}
                        disabled={approving === a.id}
                      >
                        {approving === a.id ? (
                          <Loader2 className="animate-spin" />
                        ) : (
                          <CheckCircle2 />
                        )}
                        Approve
                      </Button>
                    )}
                  </div>
                  {isOpen && (
                    <div className="flex flex-col gap-3 border-t border-border p-3">
                      {a.original_title && a.original_title !== a.title && (
                        <p className="text-xs text-muted-foreground">
                          Original: <span className="line-through">{a.original_title}</span>
                        </p>
                      )}
                      {Array.isArray(a.clo_codes) && a.clo_codes.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-xs font-medium text-muted-foreground">
                            CLOs:
                          </span>
                          {a.clo_codes.map((c, i) => (
                            <Badge key={i} variant="secondary">
                              {String(c)}
                            </Badge>
                          ))}
                        </div>
                      )}
                      <StageArtifactView
                        artifact={{
                          required_artifact: a.required_artifact,
                          output_formats: a.output_formats,
                          fixed_core: a.fixed_core,
                          personalized_variables: a.personalized_variables,
                          rubric: a.rubric,
                          integrity_requirements: a.integrity_requirements,
                          readiness_gate: a.readiness_gate,
                          context_profile_schema: a.context_profile_schema,
                        }}
                      />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* Learning hours / accreditation equivalency */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Clock className="size-4 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Learning hours & equivalency</CardTitle>
              <CardDescription>
                {creditHours != null
                  ? `Course credit hours: ${creditHours}`
                  : "Self-paced effort mapped to the credit-hour expectation."}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-24 w-full" />
          ) : effort?.artifact ? (
            <StageArtifactView artifact={effort.artifact} outputKind="effort_map" />
          ) : (
            <p className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
              No approved effort map yet. Run and approve the Learning Hours stage
              to estimate accreditation equivalency.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
