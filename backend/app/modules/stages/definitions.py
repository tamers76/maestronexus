"""The Maestro Blueprint's 18-stage process as a registry of *features*.

This mirrors the ``Maestro Blueprint.docx`` end-to-end flow. Every stage is
independent: it can be run/re-run on a course in any order. ``inputs`` lists
*soft* upstream stages — used to gather available context for the prompt, never
to gate execution.

The registry is pure data (like ``ai/providers.py``): no DB, no side effects.

Backward compatibility: four legacy ``stage_key`` values from the original
12-stage registry are kept resolvable through :data:`STAGE_ALIASES` so stored
``StageRun.stage_key`` rows (and existing API callers) keep working:

    clo_refinement      -> clo_review
    assessment_rubrics  -> assessment_weighting
    mastery_node_design -> mastery_nodes
    node_relationship_map -> node_relationships
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Stage feature spec ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StageSpec:
    """Static description of one stage feature."""

    key: str
    order: int
    title: str
    description: str
    # Soft upstream stage keys whose latest artifact is offered as context.
    inputs: list[str] = field(default_factory=list)
    # What the stage produces (informational + drives optional promotion).
    output_kind: str = "artifact"
    # Default execution mode when no tenant/stage override exists.
    default_execution: str = "single"
    # "low" | "high" — high-risk stages route to an SME for review.
    risk: str = "low"
    # Optional domain target an accepted artifact can be promoted into.
    promotes_to: str | None = None


# ── Legacy stage_key aliases (old 12-stage registry -> new canonical key) ─────

STAGE_ALIASES: dict[str, str] = {
    "clo_refinement": "clo_review",
    "assessment_rubrics": "assessment_weighting",
    "mastery_node_design": "mastery_nodes",
    "node_relationship_map": "node_relationships",
}


def canonical_key(key: str) -> str:
    """Resolve a (possibly legacy) ``stage_key`` to its canonical registry key."""

    return STAGE_ALIASES.get(key, key)


def stage_key_variants(key: str) -> list[str]:
    """All stored ``stage_key`` values that map to the same canonical stage.

    Used for reads so a query for ``clo_review`` still matches old rows stored
    as ``clo_refinement`` (and vice versa).
    """

    canon = canonical_key(key)
    variants = [canon]
    variants.extend(old for old, new in STAGE_ALIASES.items() if new == canon)
    return variants


# ── The 18 Blueprint stages ───────────────────────────────────────────────────

STAGE_REGISTRY: dict[str, StageSpec] = {
    "intake": StageSpec(
        key="intake",
        order=1,
        title="Course Intake and Syllabus Extraction",
        description=(
            "Extract the existing academic structure from the uploaded syllabus: "
            "course metadata, official CLOs, assessment components, weekly plan, "
            "readings, credit hours, delivery model, and initial risks. Extraction "
            "only — nothing is redesigned yet."
        ),
        inputs=[],
        output_kind="course_contract",
        default_execution="single",
        risk="low",
        promotes_to="course_contract",
    ),
    "clo_review": StageSpec(
        key="clo_review",
        order=2,
        title="CLO Quality Review and Refinement",
        description=(
            "Review the official CLOs and refine them into a stronger academic "
            "foundation for adaptive design. Preserves official CLOs as the "
            "accreditation starting point; proposes refined wording, evidence of "
            "mastery, role in journey, and SME decisions."
        ),
        inputs=["intake"],
        output_kind="clo_review",
        default_execution="council",
        risk="high",
        promotes_to="learning_outcome",
    ),
    "assessment_redesign": StageSpec(
        key="assessment_redesign",
        order=3,
        title="Assessment Redesign for Contribution",
        description=(
            "Redesign formal assessments into authentic, context-specific "
            "contribution artifacts. Personalizes the context, not the rigor: a "
            "fixed academic core + rubric with personalized learner context."
        ),
        inputs=["intake", "clo_review"],
        output_kind="assessment_blueprints",
        default_execution="council",
        risk="high",
        promotes_to="contribution_assessment",
    ),
    "assessment_weighting": StageSpec(
        key="assessment_weighting",
        order=4,
        title="Assessment Structure, Weighting and Rubric Review",
        description=(
            "Decide how the redesigned assessments are weighted, graded, and "
            "evaluated: number of assessments, weights, rubric criteria + weights, "
            "process-evidence and AI-use policy, and revision policy."
        ),
        inputs=["assessment_redesign", "clo_review"],
        output_kind="rubrics",
        default_execution="single",
        risk="high",
        promotes_to="contribution_assessment",
    ),
    "assessment_integrity": StageSpec(
        key="assessment_integrity",
        order=5,
        title="Assessment Integrity and Active AI Use",
        description=(
            "Design assessments for active, transparent, accountable AI use. "
            "Defines required process: context anchoring, process checkpoints, "
            "decision rationale, evidence trail, AI-use disclosure, reflection, "
            "and verification readiness."
        ),
        inputs=["assessment_redesign", "assessment_weighting"],
        output_kind="integrity_checklist",
        default_execution="single",
        risk="high",
        promotes_to="contribution_assessment",
    ),
    "subtopic_architecture": StageSpec(
        key="subtopic_architecture",
        order=6,
        title="Self-Paced Subtopic Architecture",
        description=(
            "Create the self-paced learning territories (subtopics) needed to "
            "reach the refined CLOs and prepare for the redesigned assessments. "
            "The weekly plan is scope evidence, not the structure."
        ),
        inputs=["clo_review", "assessment_redesign"],
        output_kind="subtopics",
        default_execution="council",
        risk="low",
        promotes_to="course_subtopic",
    ),
    "mastery_nodes": StageSpec(
        key="mastery_nodes",
        order=7,
        title="Mastery Node Design",
        description=(
            "Break subtopics into decision-ready Mastery Nodes — focused units of "
            "concept, judgment, application, bridge, or integration that Maestro "
            "can teach, evidence, connect, and adapt around."
        ),
        inputs=["subtopic_architecture", "clo_review"],
        output_kind="mastery_nodes",
        default_execution="council",
        risk="low",
        promotes_to="learning_node",
    ),
    "node_evidence_logic": StageSpec(
        key="node_evidence_logic",
        order=8,
        title="Node Evidence and Readiness Decision Model",
        description=(
            "Define how each node's learner evidence is interpreted into readiness "
            "states (not ready / partially ready / ready / advanced) with adaptive "
            "actions, remediation, and enrichment paths."
        ),
        inputs=["mastery_nodes"],
        output_kind="evidence_logic",
        default_execution="single",
        risk="low",
        promotes_to="learning_node",
    ),
    "node_relationships": StageSpec(
        key="node_relationships",
        order=9,
        title="Node Relationship and Bridge Map",
        description=(
            "Connect nodes within and across CLOs (prerequisite, dependency, "
            "misconception, reinforcement, transfer, integration, remediation, "
            "enrichment, and bridge relationships)."
        ),
        inputs=["mastery_nodes"],
        output_kind="node_edges",
        default_execution="single",
        risk="low",
        promotes_to="node_dependency",
    ),
    "ai_companion": StageSpec(
        key="ai_companion",
        order=10,
        title="AI Companion as Learner Journey Advisor",
        description=(
            "Configure the learner-facing AI Companion that explains progress, CLO "
            "and node readiness, recommends the next best action, and connects "
            "achievements to assessments, badges, and contribution opportunities."
        ),
        inputs=["mastery_nodes", "node_evidence_logic"],
        output_kind="companion_config",
        default_execution="single",
        risk="low",
        promotes_to="course_config",
    ),
    "readiness_gate": StageSpec(
        key="readiness_gate",
        order=11,
        title="Assessment Readiness Gate",
        description=(
            "Define the readiness gate checked before formal assessment "
            "submission: required nodes, resolved misconceptions, approved context "
            "profile, process checkpoints, AI-use disclosure, privacy, reflection, "
            "and draft quality."
        ),
        inputs=["mastery_nodes", "assessment_redesign", "assessment_integrity"],
        output_kind="readiness_gates",
        default_execution="single",
        risk="high",
        promotes_to="contribution_assessment",
    ),
    "assessment_submission": StageSpec(
        key="assessment_submission",
        order=12,
        title="Contribution Assessment Submission and Evaluation",
        description=(
            "Define the formal submission package and rubric-based evaluation "
            "workflow: artifact, context profile, decision log, AI-use disclosure, "
            "process checkpoints, reflection, and the evaluation recommendation."
        ),
        inputs=["assessment_redesign", "assessment_weighting", "readiness_gate"],
        output_kind="submission_template",
        default_execution="single",
        risk="low",
        promotes_to="workflow_template",
    ),
    "feedback_grading": StageSpec(
        key="feedback_grading",
        order=13,
        title="Feedback, Revision and Grade Finalization",
        description=(
            "Define the feedback, revision, and grade-finalization workflow: "
            "accept/revise/defend outcomes, process-evidence checks, integrity "
            "review, grade finalization, and publication recommendation."
        ),
        inputs=["assessment_submission", "assessment_weighting"],
        output_kind="grading_template",
        default_execution="single",
        risk="high",
        promotes_to="workflow_template",
    ),
    "contribution_preparation": StageSpec(
        key="contribution_preparation",
        order=14,
        title="Contribution Version Preparation",
        description=(
            "Define how a graded assessment is converted into a public-facing or "
            "internal contribution version: formats, simplification, anonymization, "
            "public summary, metadata, and visual/video adaptation."
        ),
        inputs=["feedback_grading", "assessment_redesign"],
        output_kind="contribution_template",
        default_execution="single",
        risk="low",
        promotes_to="workflow_template",
    ),
    "verified_contribution": StageSpec(
        key="verified_contribution",
        order=15,
        title="Verified Contribution",
        description=(
            "Define the verified-contribution pathway: visibility levels, "
            "verification requirements (consent, SME verification, accuracy, "
            "anonymization, references), and publication metadata."
        ),
        inputs=["contribution_preparation"],
        output_kind="verification_template",
        default_execution="single",
        risk="high",
        promotes_to="workflow_template",
    ),
    "mastery_credits": StageSpec(
        key="mastery_credits",
        order=16,
        title="Mastery Credits / Excellence Credits",
        description=(
            "Define the optional Mastery Credit currency: how credits are earned "
            "(advanced challenges, transfer, contribution-ready work) and redeemed "
            "(publication review, SME time, showcase, enrichment)."
        ),
        inputs=["mastery_nodes", "verified_contribution"],
        output_kind="credits_template",
        default_execution="single",
        risk="low",
        promotes_to="workflow_template",
    ),
    "learning_hours": StageSpec(
        key="learning_hours",
        order=17,
        title="Learning Hours and Accreditation Equivalency",
        description=(
            "Estimate the self-paced learning effort and map it to the course "
            "credit-hour expectation: core/practice/evidence/assessment/reflection "
            "time by CLO, subtopic, node, and assessment for accreditation review."
        ),
        inputs=["clo_review", "subtopic_architecture", "mastery_nodes"],
        output_kind="effort_map",
        default_execution="single",
        risk="low",
        promotes_to="effort_map",
    ),
    "analytics": StageSpec(
        key="analytics",
        order=18,
        title="Analytics, Faculty Dashboard and Continuous Improvement",
        description=(
            "Define the faculty dashboard and continuous-improvement analytics: "
            "CLO progress, node friction, misconceptions, readiness failures, "
            "AI-use trends, assessment weaknesses, publication candidates, and "
            "Mastery Credits."
        ),
        inputs=["mastery_nodes", "assessment_redesign"],
        output_kind="analytics_config",
        default_execution="single",
        risk="low",
        promotes_to="course_config",
    ),
}

# Ordered list of canonical stage keys (Stage 1 → Stage 18).
STAGE_ORDER: list[str] = [
    spec.key for spec in sorted(STAGE_REGISTRY.values(), key=lambda s: s.order)
]


def get_stage(key: str) -> StageSpec | None:
    """Look up a stage by canonical or legacy ``stage_key``."""

    return STAGE_REGISTRY.get(canonical_key(key))


def ordered_stages() -> list[StageSpec]:
    return [STAGE_REGISTRY[key] for key in STAGE_ORDER]


def aliases_for(key: str) -> list[str]:
    """Legacy ``stage_key`` aliases that resolve to ``key`` (canonical)."""

    canon = canonical_key(key)
    return [old for old, new in STAGE_ALIASES.items() if new == canon]


__all__ = [
    "StageSpec",
    "STAGE_REGISTRY",
    "STAGE_ORDER",
    "STAGE_ALIASES",
    "get_stage",
    "ordered_stages",
    "canonical_key",
    "stage_key_variants",
    "aliases_for",
]
