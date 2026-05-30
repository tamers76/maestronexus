/**
 * Typed client for the Maestro Blueprint runtime (`/api/v1/blueprint`).
 *
 * Mirrors `backend/app/modules/blueprint/schemas.py`. Covers the contribution
 * assessment blueprints (design/SME), the learner runtime (context profiles,
 * node evidence, readiness gates, submissions, contribution preparation,
 * Mastery Credits) and faculty workflows (evaluation, grading, verification,
 * publication candidates, analytics).
 *
 * Permission model (gated server-side, surfaced in the UI via `hasPermission`):
 *   - course.manage   — list/edit/approve assessment blueprints
 *   - node.progress    — learner context profile, evidence, submission, credits read
 *   - project.grade    — faculty evaluation, grading, revision, context review, awards
 *   - stage.review     — SME contribution verification, credit approval
 *   - report.view_class — analytics + publication candidates
 */

import { apiFetch } from "@/lib/api";

// ── Shared literals ───────────────────────────────────────────────────────────

export type ReadinessState = "not_ready" | "partially_ready" | "ready" | "advanced";

export type GateOutcome =
  | "ready_to_submit"
  | "ready_with_caution"
  | "needs_targeted_support"
  | "not_ready";

export type SubmissionStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "revision_requested"
  | "graded";

export type EvaluationRecommendation =
  | "accept"
  | "minor_revision"
  | "major_revision"
  | "missing_process_evidence"
  | "ai_use_clarification"
  | "defense_requested"
  | "sme_review"
  | "not_recommended";

export type VisibilityLevel = "private" | "internal" | "public";

export type VerificationStatus = "pending" | "verified" | "needs_revision" | "rejected";

export type CreditStatus = "recommended" | "approved" | "redeemed" | "rejected";

// ── Contribution assessments (design / SME) ───────────────────────────────────

export type ContributionAssessment = {
  id: string;
  course_id: string;
  course_version_id: string | null;
  assessment_key: string;
  title: string;
  original_title: string | null;
  contribution_purpose: string | null;
  clo_codes: unknown[];
  fixed_core: Record<string, unknown>;
  personalized_variables: unknown[];
  required_artifact: string | null;
  output_formats: unknown[];
  rubric: Record<string, unknown>;
  weight: number | null;
  integrity_requirements: Record<string, unknown>;
  context_profile_schema: Record<string, unknown>;
  readiness_gate: Record<string, unknown>;
  publication_potential: string | null;
  position: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ContributionAssessmentUpdate = {
  title?: string;
  contribution_purpose?: string | null;
  clo_codes?: unknown[];
  fixed_core?: Record<string, unknown>;
  personalized_variables?: unknown[];
  required_artifact?: string | null;
  output_formats?: unknown[];
  rubric?: Record<string, unknown>;
  weight?: number | null;
  integrity_requirements?: Record<string, unknown>;
  context_profile_schema?: Record<string, unknown>;
  readiness_gate?: Record<string, unknown>;
  publication_potential?: string | null;
  status?: string;
};

export function listAssessments(courseId: string): Promise<ContributionAssessment[]> {
  return apiFetch<ContributionAssessment[]>(`/blueprint/courses/${courseId}/assessments`);
}

export function getAssessment(assessmentId: string): Promise<ContributionAssessment> {
  return apiFetch<ContributionAssessment>(`/blueprint/assessments/${assessmentId}`);
}

export function updateAssessment(
  assessmentId: string,
  payload: ContributionAssessmentUpdate,
): Promise<ContributionAssessment> {
  return apiFetch<ContributionAssessment>(`/blueprint/assessments/${assessmentId}`, {
    method: "PATCH",
    json: payload,
  });
}

export function approveAssessment(assessmentId: string): Promise<ContributionAssessment> {
  return apiFetch<ContributionAssessment>(
    `/blueprint/assessments/${assessmentId}/approve`,
    { method: "POST" },
  );
}

// ── Context profile ────────────────────────────────────────────────────────────

export type ContextProfile = {
  id: string;
  assessment_id: string;
  enrollment_id: string;
  profile: Record<string, unknown>;
  status: string;
  reviewed_by: string | null;
  review_note: string | null;
  created_at: string;
  updated_at: string;
};

export function submitContextProfile(
  assessmentId: string,
  input: { enrollment_id: string; profile: Record<string, unknown> },
): Promise<ContextProfile> {
  return apiFetch<ContextProfile>(
    `/blueprint/assessments/${assessmentId}/context-profile`,
    { method: "POST", json: input },
  );
}

export function reviewContextProfile(
  profileId: string,
  input: { approve: boolean; note?: string | null },
): Promise<ContextProfile> {
  return apiFetch<ContextProfile>(`/blueprint/context-profiles/${profileId}/review`, {
    method: "POST",
    json: input,
  });
}

// ── Node evidence + readiness ─────────────────────────────────────────────────

export type NodeEvidence = {
  id: string;
  enrollment_id: string;
  node_id: string;
  evidence: Record<string, unknown>;
  readiness_state: string;
  feedback: Record<string, unknown>;
  ai_companion_message: string | null;
  created_at: string;
};

export type NodeEvidenceResult = {
  evidence: NodeEvidence;
  readiness_state: string;
  ai_companion_message: string | null;
};

export function submitNodeEvidence(
  enrollmentId: string,
  nodeId: string,
  input: { evidence: Record<string, unknown>; readiness_state?: ReadinessState | null },
): Promise<NodeEvidenceResult> {
  return apiFetch<NodeEvidenceResult>(
    `/blueprint/enrollments/${enrollmentId}/nodes/${nodeId}/evidence`,
    { method: "POST", json: input },
  );
}

export function listNodeEvidence(
  enrollmentId: string,
  nodeId: string,
): Promise<NodeEvidence[]> {
  return apiFetch<NodeEvidence[]>(
    `/blueprint/enrollments/${enrollmentId}/nodes/${nodeId}/evidence`,
  );
}

// ── Readiness gate ─────────────────────────────────────────────────────────────

export type GateCheck = {
  check: string;
  passed: boolean;
  detail: string | null;
};

export type ReadinessGateResult = {
  assessment_id: string;
  enrollment_id: string;
  outcome: GateOutcome;
  checks: GateCheck[];
  missing_node_keys: string[];
  context_profile_approved: boolean;
};

export function checkReadiness(
  assessmentId: string,
  enrollmentId: string,
): Promise<ReadinessGateResult> {
  return apiFetch<ReadinessGateResult>(
    `/blueprint/assessments/${assessmentId}/readiness?enrollment_id=${encodeURIComponent(
      enrollmentId,
    )}`,
  );
}

// ── Submissions ────────────────────────────────────────────────────────────────

export type Submission = {
  id: string;
  assessment_id: string;
  enrollment_id: string;
  context_profile_id: string | null;
  package: Record<string, unknown>;
  version: number;
  status: SubmissionStatus | string;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
};

export function createSubmission(
  assessmentId: string,
  input: { enrollment_id: string; package: Record<string, unknown>; submit: boolean },
): Promise<Submission> {
  return apiFetch<Submission>(`/blueprint/assessments/${assessmentId}/submissions`, {
    method: "POST",
    json: input,
  });
}

export function getSubmission(submissionId: string): Promise<Submission> {
  return apiFetch<Submission>(`/blueprint/submissions/${submissionId}`);
}

export function updateSubmission(
  submissionId: string,
  pkg: Record<string, unknown>,
): Promise<Submission> {
  return apiFetch<Submission>(`/blueprint/submissions/${submissionId}`, {
    method: "PATCH",
    json: { package: pkg },
  });
}

export function submitSubmission(submissionId: string): Promise<Submission> {
  return apiFetch<Submission>(`/blueprint/submissions/${submissionId}/submit`, {
    method: "POST",
  });
}

export function listSubmissions(params: {
  assessment_id?: string;
  enrollment_id?: string;
}): Promise<Submission[]> {
  const search = new URLSearchParams();
  if (params.assessment_id) search.set("assessment_id", params.assessment_id);
  if (params.enrollment_id) search.set("enrollment_id", params.enrollment_id);
  const q = search.toString();
  return apiFetch<Submission[]>(`/blueprint/submissions${q ? `?${q}` : ""}`);
}

// ── Evaluation / grading (faculty) ───────────────────────────────────────────

export type Evaluation = {
  id: string;
  submission_id: string;
  rubric_scores: Record<string, unknown>;
  recommendation: string | null;
  feedback_learner: string | null;
  feedback_sme: string | null;
  integrity_flag: boolean;
  publication_potential: string | null;
  grade: number | null;
  finalized: boolean;
  evaluator_kind: string;
  evaluated_by: string | null;
  created_at: string;
  updated_at: string;
};

export type EvaluationCreate = {
  rubric_scores?: Record<string, number>;
  recommendation?: EvaluationRecommendation | null;
  feedback_learner?: string | null;
  feedback_sme?: string | null;
  integrity_flag?: boolean;
  publication_potential?: string | null;
  grade?: number | null;
  evaluator_kind?: "ai" | "sme";
};

export function evaluateSubmission(
  submissionId: string,
  input: EvaluationCreate,
): Promise<Evaluation> {
  return apiFetch<Evaluation>(`/blueprint/submissions/${submissionId}/evaluate`, {
    method: "POST",
    json: input,
  });
}

export function finalizeGrade(
  submissionId: string,
  input: { grade: number; feedback_learner?: string | null; publication_potential?: string | null },
): Promise<Evaluation> {
  return apiFetch<Evaluation>(`/blueprint/submissions/${submissionId}/finalize-grade`, {
    method: "POST",
    json: input,
  });
}

export function requestRevision(
  submissionId: string,
  input: { kind: "minor" | "major"; note?: string | null },
): Promise<Submission> {
  return apiFetch<Submission>(`/blueprint/submissions/${submissionId}/request-revision`, {
    method: "POST",
    json: input,
  });
}

export function getEvaluation(submissionId: string): Promise<Evaluation | null> {
  return apiFetch<Evaluation | null>(`/blueprint/submissions/${submissionId}/evaluation`);
}

// ── Contribution versions ────────────────────────────────────────────────────

export type Contribution = {
  id: string;
  submission_id: string | null;
  enrollment_id: string;
  format: string | null;
  title: string | null;
  summary: string | null;
  body: Record<string, unknown>;
  metadata: Record<string, unknown>;
  consent: boolean;
  anonymized: boolean;
  visibility_level: VisibilityLevel | string;
  verification_status: VerificationStatus | string;
  license: string | null;
  verified_by: string | null;
  created_at: string;
  updated_at: string;
};

export type ContributionCreate = {
  format?: string | null;
  title?: string | null;
  summary?: string | null;
  body?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  consent?: boolean;
  anonymized?: boolean;
  visibility_level?: VisibilityLevel;
  license?: string | null;
};

export type ContributionUpdate = ContributionCreate;

export function prepareContribution(
  submissionId: string,
  input: ContributionCreate,
): Promise<Contribution> {
  return apiFetch<Contribution>(`/blueprint/submissions/${submissionId}/contribution`, {
    method: "POST",
    json: input,
  });
}

export function updateContribution(
  contributionId: string,
  input: ContributionUpdate,
): Promise<Contribution> {
  return apiFetch<Contribution>(`/blueprint/contributions/${contributionId}`, {
    method: "PATCH",
    json: input,
  });
}

export function verifyContribution(
  contributionId: string,
  input: {
    verification_status: VerificationStatus;
    visibility_level?: VisibilityLevel | null;
    note?: string | null;
  },
): Promise<Contribution> {
  return apiFetch<Contribution>(`/blueprint/contributions/${contributionId}/verify`, {
    method: "POST",
    json: input,
  });
}

export function listEnrollmentContributions(enrollmentId: string): Promise<Contribution[]> {
  return apiFetch<Contribution[]>(`/blueprint/enrollments/${enrollmentId}/contributions`);
}

export function listPublicationCandidates(courseId: string): Promise<Contribution[]> {
  return apiFetch<Contribution[]>(`/blueprint/courses/${courseId}/contributions`);
}

// ── Mastery credits ────────────────────────────────────────────────────────────

export type Credit = {
  id: string;
  enrollment_id: string;
  source_type: string;
  source_id: string | null;
  amount: number;
  rationale: string | null;
  status: CreditStatus | string;
  redeemed_for: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
};

export function listCredits(enrollmentId: string): Promise<Credit[]> {
  return apiFetch<Credit[]>(`/blueprint/enrollments/${enrollmentId}/credits`);
}

export function awardCredit(
  enrollmentId: string,
  input: {
    source_type: "node" | "assessment" | "contribution" | "other";
    source_id?: string | null;
    amount: number;
    rationale?: string | null;
  },
): Promise<Credit> {
  return apiFetch<Credit>(`/blueprint/enrollments/${enrollmentId}/credits`, {
    method: "POST",
    json: input,
  });
}

export function approveCredit(creditId: string): Promise<Credit> {
  return apiFetch<Credit>(`/blueprint/credits/${creditId}/approve`, { method: "POST" });
}

export function redeemCredit(creditId: string, redeemedFor: string): Promise<Credit> {
  return apiFetch<Credit>(`/blueprint/credits/${creditId}/redeem`, {
    method: "POST",
    json: { redeemed_for: redeemedFor },
  });
}

// ── Faculty analytics ────────────────────────────────────────────────────────

export type CourseAnalytics = {
  course_id: string;
  readiness_states: Record<string, number>;
  submissions_by_status: Record<string, number>;
  evaluations: { finalized?: number; pending?: number; average_grade?: number | null } & Record<
    string,
    unknown
  >;
  publication_candidates: number;
  mastery_credits: { recommended?: number; approved?: number; redeemed?: number } & Record<
    string,
    unknown
  >;
  continuous_improvement: Record<string, unknown> | null;
};

export function getCourseAnalytics(courseId: string): Promise<CourseAnalytics> {
  return apiFetch<CourseAnalytics>(`/blueprint/courses/${courseId}/analytics`);
}

// ── Display helpers (shared across Studio / learner / faculty) ────────────────

export const READINESS_META: Record<
  ReadinessState,
  { label: string; variant: "outline" | "secondary" | "warning" | "success" | "default" }
> = {
  not_ready: { label: "Not ready", variant: "outline" },
  partially_ready: { label: "Partially ready", variant: "warning" },
  ready: { label: "Ready", variant: "success" },
  advanced: { label: "Advanced", variant: "default" },
};

export const GATE_OUTCOME_META: Record<
  GateOutcome,
  { label: string; variant: "outline" | "secondary" | "warning" | "success" | "destructive" }
> = {
  ready_to_submit: { label: "Ready to submit", variant: "success" },
  ready_with_caution: { label: "Ready with caution", variant: "warning" },
  needs_targeted_support: { label: "Needs targeted support", variant: "warning" },
  not_ready: { label: "Not ready", variant: "destructive" },
};

export const SUBMISSION_STATUS_META: Record<
  string,
  { label: string; variant: "outline" | "secondary" | "warning" | "success" | "destructive" }
> = {
  draft: { label: "Draft", variant: "outline" },
  submitted: { label: "Submitted", variant: "warning" },
  under_review: { label: "Under review", variant: "secondary" },
  revision_requested: { label: "Revision requested", variant: "destructive" },
  graded: { label: "Graded", variant: "success" },
};

export const VERIFICATION_META: Record<
  string,
  { label: string; variant: "outline" | "secondary" | "warning" | "success" | "destructive" }
> = {
  pending: { label: "Pending", variant: "warning" },
  verified: { label: "Verified", variant: "success" },
  needs_revision: { label: "Needs revision", variant: "secondary" },
  rejected: { label: "Rejected", variant: "destructive" },
};

export const CREDIT_STATUS_META: Record<
  string,
  { label: string; variant: "outline" | "secondary" | "warning" | "success" | "destructive" }
> = {
  recommended: { label: "Recommended", variant: "warning" },
  approved: { label: "Approved", variant: "success" },
  redeemed: { label: "Redeemed", variant: "secondary" },
  rejected: { label: "Rejected", variant: "destructive" },
};
