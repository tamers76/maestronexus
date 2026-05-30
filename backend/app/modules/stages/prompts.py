"""Per-stage prompts: recommended member/chairman system prompts + builders.

Adapted from the spirit of DeepT's ``recommendedPrompts`` and tailored to the
docx's 12 Maestro stages. ``RECOMMENDED_PROMPTS`` provides sensible defaults the
admin can edit (and reset to) per stage in Settings. ``build_user_prompt``
assembles the per-run user message from the course + any available upstream
stage artifacts.
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

    lines.append(
        "\nReturn the artifact now. Include a top-level \"gaps\" array listing any "
        "missing inputs or assumptions an SME should confirm."
    )
    return "\n".join(lines)


__all__ = ["RECOMMENDED_PROMPTS", "recommended_prompts", "build_user_prompt"]
