"""The 12-stage Maestro process as a registry of *features* (not a sequence).

This mirrors the ``Maestro .docx`` process and the spirit of DeepT's stage
pipeline, but every stage here is independent: it can be run/re-run on a course
in any order. ``inputs`` lists *soft* upstream stages — used to gather available
context for the prompt, never to gate execution.

The registry is pure data (like ``ai/providers.py``): no DB, no side effects.
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


# ── The 12 stages ─────────────────────────────────────────────────────────────

STAGE_REGISTRY: dict[str, StageSpec] = {
    "intake": StageSpec(
        key="intake",
        order=1,
        title="Course Intake",
        description=(
            "Ingest the syllabus (text/PDF/DOCX) and extract the course contract: "
            "CLOs, weekly topics, readings, assessments, weights, and credit-hour "
            "expectations. Treats the upload as starting evidence, not the final course."
        ),
        inputs=[],
        output_kind="course_contract",
        default_execution="single",
        risk="low",
    ),
    "clo_refinement": StageSpec(
        key="clo_refinement",
        order=2,
        title="CLO Refinement",
        description="Strengthen Course Learning Outcomes for adaptive, measurable design.",
        inputs=["intake"],
        output_kind="refined_clos",
        default_execution="single",
        risk="low",
        promotes_to="learning_outcome",
    ),
    "assessment_redesign": StageSpec(
        key="assessment_redesign",
        order=3,
        title="Assessment Redesign",
        description=(
            "Turn assessments into contribution artifacts: same standard, personalized "
            "context, rubric-based, AI-integrity aware."
        ),
        inputs=["intake", "clo_refinement"],
        output_kind="assessment_blueprints",
        default_execution="single",
        risk="high",
    ),
    "assessment_rubrics": StageSpec(
        key="assessment_rubrics",
        order=4,
        title="Assessment Structure and Rubrics",
        description="Review weights, grading logic, and rubrics for SME approval.",
        inputs=["assessment_redesign"],
        output_kind="rubrics",
        default_execution="single",
        risk="high",
    ),
    "subtopic_architecture": StageSpec(
        key="subtopic_architecture",
        order=5,
        title="Subtopic Architecture",
        description="Transform the course into self-paced learning territories (subtopics).",
        inputs=["clo_refinement"],
        output_kind="subtopics",
        default_execution="single",
        risk="low",
    ),
    "mastery_node_design": StageSpec(
        key="mastery_node_design",
        order=6,
        title="Mastery Node Design",
        description="Break subtopics into decision-ready Mastery Nodes (units of mastery).",
        inputs=["subtopic_architecture", "clo_refinement"],
        output_kind="mastery_nodes",
        default_execution="single",
        risk="low",
        promotes_to="learning_node",
    ),
    "node_evidence_logic": StageSpec(
        key="node_evidence_logic",
        order=7,
        title="Node Evidence and Readiness Logic",
        description=(
            "Define how learner evidence is interpreted: success criteria, "
            "readiness states, feedback rules, remediation and challenge paths."
        ),
        inputs=["mastery_node_design"],
        output_kind="evidence_logic",
        default_execution="single",
        risk="low",
    ),
    "node_relationship_map": StageSpec(
        key="node_relationship_map",
        order=8,
        title="Node Relationship Map",
        description="Connect nodes inside and across CLOs (prerequisite / mastery edges).",
        inputs=["mastery_node_design"],
        output_kind="node_edges",
        default_execution="single",
        risk="low",
        promotes_to="node_dependency",
    ),
    "node_experience": StageSpec(
        key="node_experience",
        order=9,
        title="Node Experience Assembly",
        description="Turn each node into learning blocks (the learner-facing experience).",
        inputs=["mastery_node_design", "node_evidence_logic"],
        output_kind="node_blueprints",
        default_execution="single",
        risk="low",
    ),
    "content_production": StageSpec(
        key="content_production",
        order=10,
        title="Content Production and Orchestration",
        description=(
            "Produce block-level instructional content per node. Council mode is "
            "recommended here for quality; output lands in the human-review flow."
        ),
        inputs=["node_experience", "mastery_node_design"],
        output_kind="content_blocks",
        default_execution="council",
        risk="low",
        promotes_to="ai_generated_content",
    ),
    "course_assembly": StageSpec(
        key="course_assembly",
        order=11,
        title="Course Assembly Map",
        description=(
            "Assemble nodes, blocks, assets, rules, and assessments into an "
            "LMS-ready course assembly map."
        ),
        inputs=[
            "mastery_node_design",
            "node_relationship_map",
            "content_production",
            "assessment_rubrics",
        ],
        output_kind="assembly_map",
        default_execution="single",
        risk="low",
    ),
    "learner_journey": StageSpec(
        key="learner_journey",
        order=12,
        title="Learner Journey and Adaptivity",
        description=(
            "Define the learner experience: evidence interpretation, feedback, and "
            "next-best-action adaptivity that hooks into the adaptive engine."
        ),
        inputs=["course_assembly", "node_evidence_logic"],
        output_kind="adaptivity_config",
        default_execution="single",
        risk="low",
    ),
}

# Ordered list of stage keys (Stage 1 → Stage 12).
STAGE_ORDER: list[str] = [
    spec.key for spec in sorted(STAGE_REGISTRY.values(), key=lambda s: s.order)
]


def get_stage(key: str) -> StageSpec | None:
    return STAGE_REGISTRY.get(key)


def ordered_stages() -> list[StageSpec]:
    return [STAGE_REGISTRY[key] for key in STAGE_ORDER]


__all__ = ["StageSpec", "STAGE_REGISTRY", "STAGE_ORDER", "get_stage", "ordered_stages"]
