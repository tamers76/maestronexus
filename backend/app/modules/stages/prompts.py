"""Per-stage prompts: recommended member/chairman system prompts + builders.

Tailored to the Maestro Blueprint's 18 stages. ``RECOMMENDED_PROMPTS`` provides
sensible defaults the admin can edit (and reset to) per stage in Settings.
``build_user_prompt`` assembles the per-run user message from the course + any
available upstream stage artifacts.

Every stage's output schema includes a top-level ``gaps`` array and (where an
SME decision is implied) ``sme_decisions``, plus stable identifiers so approved
artifacts can be promoted into domain rows idempotently.
"""

from __future__ import annotations

import json
from typing import Any

from app.modules.stages.definitions import STAGE_REGISTRY, StageSpec

# A shared base that nudges every member toward accreditation-safe, structured,
# JSON-friendly output that an SME can review.
_MEMBER_BASE = (
    "You are a Council Member in an AI governance workflow for designing an "
    "accreditable, adaptive university course (the Maestro system). Produce the "
    "Stage '{title}' artifact.\n\n"
    "Hard rules:\n"
    "- Be specific, accurate, and pedagogically sound.\n"
    "- Prefer a single valid JSON object as your answer (no markdown fences).\n"
    "- Do NOT invent institutional policies; mark unknowns as \"unknown\".\n"
    "- Respect upstream artifacts when present; if an input is missing, note the "
    "gap in a \"gaps\" array rather than fabricating it.\n\n"
    "Task: {description}"
)

_CHAIRMAN_BASE = (
    "You are the Chairman model for Stage '{title}' of the Maestro course design "
    "council. You will receive several council member responses to the same task.\n\n"
    "Your job:\n"
    "1) Synthesize ONE final artifact that takes the best, most accurate parts of "
    "each member and resolves conflicts.\n"
    "2) Keep it internally coherent and aligned to the upstream artifacts.\n"
    "3) Prefer a single valid JSON object (no markdown fences).\n"
    "4) End with a short human-readable section labeled \"SME Summary:\" listing "
    "what was decided and what an SME should verify.\n\n"
    "Stage task: {description}"
)


def _default_member(spec: StageSpec) -> str:
    return _MEMBER_BASE.format(title=spec.title, description=spec.description)


def _default_chairman(spec: StageSpec) -> str:
    return _CHAIRMAN_BASE.format(title=spec.title, description=spec.description)


# Recommended prompts for every stage, derived from its spec. Stored as plain
# strings so the admin can override them per stage and reset back to these.
RECOMMENDED_PROMPTS: dict[str, dict[str, str]] = {
    key: {
        "member_system_prompt": _default_member(spec),
        "chairman_system_prompt": _default_chairman(spec),
    }
    for key, spec in STAGE_REGISTRY.items()
}


# Stronger, stage-specific system prompts for the two CLO-bearing stages so that
# Course Intake parses a syllabus like DeepT's Stage 1, and CLO Refinement
# strengthens CLOs for adaptive, measurable design (Maestro .docx Stage 2).
RECOMMENDED_PROMPTS["intake"] = {
    "member_system_prompt": (
        "You are a curriculum analyst performing Course Intake for the Maestro "
        "system. Read the provided syllabus / source text and extract the course "
        "contract.\n\n"
        "Hard rules:\n"
        "- Extract, do not invent. Copy Course Learning Outcomes (CLOs) verbatim.\n"
        "- If a field is absent in the source, use a sensible empty value and list "
        "it in \"gaps\" rather than fabricating it.\n"
        "- Answer with a single valid JSON object only (no markdown fences)."
    ),
    "chairman_system_prompt": (
        "You are the Chairman for Course Intake. Merge the council members' "
        "extractions into ONE accurate course contract JSON object. Prefer "
        "verbatim CLOs and the most complete weekly plan / assessments. No markdown "
        "fences; end with a short \"SME Summary:\" of what to verify."
    ),
}
RECOMMENDED_PROMPTS["clo_review"] = {
    "member_system_prompt": (
        "You are part of the Maestro Curriculum Re-Engineering Council reviewing "
        "Course Learning Outcomes. Treat official CLOs as the accreditation "
        "starting point, not wording that must be blindly reused for adaptive "
        "design.\n\n"
        "For each CLO evaluate clarity, cognitive demand, scope, assessability, "
        "context of application, course alignment, relationship to other CLOs, "
        "progression, expected evidence of mastery, and adaptivity readiness.\n"
        "Keep each CLO's original code so refinements match back to intake.\n"
        "Answer with a single valid JSON object only (no markdown fences). The SME "
        "remains the academic owner — propose, do not finalize."
    ),
    "chairman_system_prompt": (
        "You are the Chairman of the Maestro CLO Review Council. Consolidate the "
        "members' independent reviews into ONE CLO Review and Refinement Report. "
        "Preserve official CLOs as the accreditation starting point, synthesize the "
        "strongest refined wording, show the proposed learning journey across CLOs, "
        "and highlight SME decisions. Preserve each CLO's code. No markdown fences; "
        "end with a short \"SME Summary:\" of what to verify."
    ),
}


# Per-stage output schema instructions appended to the user prompt so the model
# returns a machine-parsable artifact the app can promote into domain rows.
_STAGE_OUTPUT_SCHEMAS: dict[str, str] = {
    "intake": (
        "\nReturn ONE JSON object with EXACTLY this shape (no markdown fences):\n"
        "{\n"
        '  "course_code": string,\n'
        '  "title": string,\n'
        '  "description": string,\n'
        '  "credit_hours": number,\n'
        '  "weekly_plan": [{"week": number, "topic": string, "description": string, '
        '"readings": string}],\n'
        '  "clos": [{"code": string, "statement": string, "bloom_level": string, '
        '"knowledge_type": string, "measurable": boolean}],\n'
        '  "assessments": [{"name": string, "type": string, "weight": number, '
        '"description": string}],\n'
        '  "references": [string],\n'
        '  "accreditation_tags": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Copy every Course Learning Outcome from the syllabus verbatim into \"clos\". "
        "If none are present, return an empty array and note it in \"gaps\"."
    ),
    "clo_review": (
        "\nUsing the intake course_contract (especially its \"clos\"), review and "
        "refine EACH CLO for adaptive, measurable design. Return ONE JSON object "
        "(no markdown fences):\n"
        "{\n"
        '  "clos": [{\n'
        '    "code": string,\n'
        '    "original_statement": string,\n'
        '    "statement": string,\n'
        '    "diagnosis": string,\n'
        '    "bloom_level": string,\n'
        '    "knowledge_type": string,\n'
        '    "action_verb": string,\n'
        '    "measurable": boolean,\n'
        '    "capability_statement": string,\n'
        '    "evidence_of_mastery": string,\n'
        '    "role_in_journey": string,\n'
        '    "adaptive_readiness": string,\n'
        '    "rationale": string,\n'
        '    "sme_decision": "approve|edit|reject"\n'
        "  }],\n"
        '  "learning_journey": [string],\n'
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Preserve each CLO's \"code\" from the intake contract so refinements match "
        "back to the originals."
    ),
    "assessment_redesign": (
        "\nRedesign EACH assessment into a contribution artifact. Return ONE JSON "
        "object (no markdown fences):\n"
        "{\n"
        '  "assessments": [{\n'
        '    "key": string,\n'
        '    "original_title": string,\n'
        '    "title": string,\n'
        '    "diagnosis": string,\n'
        '    "clo_codes": [string],\n'
        '    "contribution_purpose": string,\n'
        '    "fixed_core": {"required_capability": string, "minimum_standard": string},\n'
        '    "personalized_variables": [string],\n'
        '    "required_artifact": string,\n'
        '    "output_formats": [string],\n'
        '    "rubric_criteria": [{"criterion": string, "description": string}],\n'
        '    "readiness_gate_needs": [string],\n'
        '    "ai_integrity_features": [string],\n'
        '    "publication_potential": "none|possible|strong",\n'
        '    "sme_decision": "approve|edit|reject"\n'
        "  }],\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Keep a stable \"key\" per assessment so weighting/integrity/readiness can "
        "match back to it."
    ),
    "assessment_weighting": (
        "\nDecide weighting, grading, and rubric logic for the redesigned "
        "assessments. Return ONE JSON object (no markdown fences):\n"
        "{\n"
        '  "assessments": [{\n'
        '    "key": string,\n'
        '    "title": string,\n'
        '    "clo_codes": [string],\n'
        '    "current_weight": number,\n'
        '    "proposed_weight": number,\n'
        '    "rationale": string,\n'
        '    "rubric": [{"criterion": string, "weight": number}],\n'
        '    "required_process_evidence": [string],\n'
        '    "grading_policy": string,\n'
        '    "revision_policy": "allowed|not_allowed|conditional"\n'
        "  }],\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Use the SAME \"key\" per assessment as the redesign stage."
    ),
    "assessment_integrity": (
        "\nDesign each assessment for active, transparent, accountable AI use. "
        "Return ONE JSON object (no markdown fences):\n"
        "{\n"
        '  "assessments": [{\n'
        '    "key": string,\n'
        '    "title": string,\n'
        '    "required_process": [string],\n'
        '    "integrity_layers": [string],\n'
        '    "ai_use_disclosure_fields": [string],\n'
        '    "passive_ai_risks": [string],\n'
        '    "recommended_changes": [string]\n'
        "  }],\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Use the SAME \"key\" per assessment as the redesign stage."
    ),
    "subtopic_architecture": (
        "\nCreate the self-paced subtopic architecture. Return ONE JSON object "
        "(no markdown fences):\n"
        "{\n"
        '  "subtopics": [{\n'
        '    "key": string,\n'
        '    "clo_code": string,\n'
        '    "title": string,\n'
        '    "purpose": string,\n'
        '    "assessment_connection": string,\n'
        '    "learning_function": string,\n'
        '    "expected_learning": string,\n'
        '    "node_families": [string],\n'
        '    "cross_clo_links": [string],\n'
        '    "estimated_effort": "low|moderate|high",\n'
        '    "recommendation": "keep|merge|split|move|remove",\n'
        '    "sme_decision": "approve|edit|reject"\n'
        "  }],\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Do not copy the weekly plan as the structure. Keep a stable \"key\" per "
        "subtopic."
    ),
    "mastery_nodes": (
        "\nCreate decision-ready Mastery Nodes. Return ONE JSON object (no markdown "
        "fences):\n"
        "{\n"
        '  "nodes": [{\n'
        '    "key": string,\n'
        '    "title": string,\n'
        '    "node_type": string,\n'
        '    "clo_code": string,\n'
        '    "subtopic_key": string,\n'
        '    "mastery_statement": string,\n'
        '    "why_it_matters": string,\n'
        '    "prerequisites": [string],\n'
        '    "dependencies": [string],\n'
        '    "misconceptions": [string],\n'
        '    "evidence_task": string,\n'
        '    "sufficient_evidence": string,\n'
        '    "assessment_connection": string,\n'
        '    "ai_companion_guidance": string,\n'
        '    "estimated_duration_minutes": number\n'
        "  }],\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Use a stable \"key\" per node; reference prerequisites/dependencies by "
        "those keys."
    ),
    "node_evidence_logic": (
        "\nDefine how each node's evidence is interpreted. Return ONE JSON object "
        "(no markdown fences):\n"
        "{\n"
        '  "nodes": [{\n'
        '    "key": string,\n'
        '    "title": string,\n'
        '    "evidence_task": string,\n'
        '    "sufficient_evidence": string,\n'
        '    "not_ready_indicators": [string],\n'
        '    "partially_ready_indicators": [string],\n'
        '    "ready_indicators": [string],\n'
        '    "advanced_indicators": [string],\n'
        '    "adaptive_actions": {"not_ready": string, "partially_ready": string, '
        '"ready": string, "advanced": string},\n'
        '    "feedback_message": string,\n'
        '    "node_role": "formative|milestone_preparatory|assessment_critical"\n'
        "  }],\n"
        '  "gaps": [string]\n'
        "}\n"
        "Use the SAME \"key\" per node as the mastery-node stage."
    ),
    "node_relationships": (
        "\nMap relationships between nodes. Return ONE JSON object (no markdown "
        "fences):\n"
        "{\n"
        '  "relationships": [{\n'
        '    "source_key": string,\n'
        '    "target_key": string,\n'
        '    "relationship_type": "prerequisite|dependency|misconception|'
        'reinforcement|transfer|integration|remediation|enrichment|bridge",\n'
        '    "why_it_matters": string,\n'
        '    "adaptive_decision": string,\n'
        '    "cross_clo": boolean\n'
        "  }],\n"
        '  "gaps": [string]\n'
        "}\n"
        "Reference nodes by their stable \"key\" from the mastery-node stage."
    ),
    "ai_companion": (
        "\nConfigure the AI Companion. Return ONE JSON object (no markdown fences):\n"
        "{\n"
        '  "companion": {\n'
        '    "tone": string,\n'
        '    "surfaced_signals": [string],\n'
        '    "recommendation_rules": [string],\n'
        '    "example_messages": [string]\n'
        "  },\n"
        '  "gaps": [string]\n'
        "}"
    ),
    "readiness_gate": (
        "\nDefine the assessment readiness gate(s). Return ONE JSON object (no "
        "markdown fences):\n"
        "{\n"
        '  "gates": [{\n'
        '    "assessment_key": string,\n'
        '    "required_node_keys": [string],\n'
        '    "checks": [{"check": string, "purpose": string}],\n'
        '    "outcomes": ["ready_to_submit", "ready_with_caution", '
        '"needs_targeted_support", "not_ready"]\n'
        "  }],\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}\n"
        "Reference assessments/nodes by their stable keys."
    ),
    "assessment_submission": (
        "\nDefine the submission + evaluation workflow. Return ONE JSON object (no "
        "markdown fences):\n"
        "{\n"
        '  "submission": {\n'
        '    "package_fields": [string],\n'
        '    "evaluation_fields": [string],\n'
        '    "evaluation_actors": [string]\n'
        "  },\n"
        '  "gaps": [string]\n'
        "}"
    ),
    "feedback_grading": (
        "\nDefine the feedback/revision/grade-finalization workflow. Return ONE "
        "JSON object (no markdown fences):\n"
        "{\n"
        '  "workflow": {\n'
        '    "outcomes": [string],\n'
        '    "revision_policy": string,\n'
        '    "grade_finalization_rules": [string],\n'
        '    "publication_trigger": string\n'
        "  },\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}"
    ),
    "contribution_preparation": (
        "\nDefine how graded work becomes a contribution version. Return ONE JSON "
        "object (no markdown fences):\n"
        "{\n"
        '  "contribution": {\n'
        '    "formats": [string],\n'
        '    "conversion_tasks": [string],\n'
        '    "metadata_fields": [string]\n'
        "  },\n"
        '  "gaps": [string]\n'
        "}"
    ),
    "verified_contribution": (
        "\nDefine the verified-contribution pathway. Return ONE JSON object (no "
        "markdown fences):\n"
        "{\n"
        '  "verification": {\n'
        '    "visibility_levels": [string],\n'
        '    "requirements": [string],\n'
        '    "metadata_fields": [string]\n'
        "  },\n"
        '  "sme_decisions": [string],\n'
        '  "gaps": [string]\n'
        "}"
    ),
    "mastery_credits": (
        "\nDefine the Mastery Credit currency. Return ONE JSON object (no markdown "
        "fences):\n"
        "{\n"
        '  "credits": {\n'
        '    "earned_through": [string],\n'
        '    "redeemed_for": [string],\n'
        '    "award_rules": [{"activity": string, "credits": number}]\n'
        "  },\n"
        '  "gaps": [string]\n'
        "}"
    ),
    "learning_hours": (
        "\nEstimate learning effort and credit-hour equivalency. Return ONE JSON "
        "object (no markdown fences):\n"
        "{\n"
        '  "total_estimated_hours": number,\n'
        '  "by_clo": [{"clo_code": string, "estimated_hours": number}],\n'
        '  "breakdown": {"core": number, "practice": number, "evidence": number, '
        '"assessment_prep": number, "artifact_creation": number, "reflection": '
        'number, "remediation": number, "enrichment": number},\n'
        '  "accreditation_alignment": string,\n'
        '  "gaps": [string]\n'
        "}"
    ),
    "analytics": (
        "\nDefine the faculty dashboard + continuous improvement analytics. Return "
        "ONE JSON object (no markdown fences):\n"
        "{\n"
        '  "dashboard": {"metrics": [string]},\n'
        '  "continuous_improvement": {"questions": [string], '
        '"recommendations": [string]},\n'
        '  "gaps": [string]\n'
        "}"
    ),
}


def recommended_prompts(stage_key: str) -> dict[str, str]:
    """Recommended member + chairman prompts for a stage (empty dict if unknown)."""

    return dict(RECOMMENDED_PROMPTS.get(stage_key, {}))


def _truncate(text: str, *, limit: int = 4000) -> str:
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…(truncated)"


def build_user_prompt(
    *,
    spec: StageSpec,
    course_title: str,
    course_description: str | None,
    options: dict[str, Any] | None,
    upstream: dict[str, Any],
) -> str:
    """Assemble the per-run user message.

    ``upstream`` maps available upstream stage_key -> its latest artifact output.
    Missing upstream inputs are surfaced explicitly so the model reports gaps
    instead of hallucinating them (stage independence).
    """

    lines: list[str] = [
        f"Course: {course_title}",
    ]
    if course_description:
        lines.append(f"Course description: {course_description}")
    lines.append(f"Stage: {spec.title} — {spec.description}")

    options = options or {}
    syllabus_text = options.get("syllabus_text")
    if syllabus_text:
        lines.append("\nSyllabus / source text:\n" + _truncate(str(syllabus_text)))
    instructions = options.get("instructions")
    if instructions:
        lines.append(f"\nAdditional instructions: {instructions}")

    if spec.inputs:
        lines.append("\nUpstream artifacts:")
        for dep in spec.inputs:
            if dep in upstream and upstream[dep] is not None:
                blob = json.dumps(upstream[dep], default=str)
                lines.append(f"- {dep}: {_truncate(blob, limit=2500)}")
            else:
                lines.append(f"- {dep}: (MISSING — not yet run; note this as a gap)")

    schema = _STAGE_OUTPUT_SCHEMAS.get(spec.key)
    if schema:
        lines.append(schema)
    else:
        lines.append(
            "\nReturn the artifact now. Include a top-level \"gaps\" array listing any "
            "missing inputs or assumptions an SME should confirm."
        )
    return "\n".join(lines)


__all__ = ["RECOMMENDED_PROMPTS", "recommended_prompts", "build_user_prompt"]
