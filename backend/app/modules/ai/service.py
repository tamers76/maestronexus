"""AI service: retrieval-grounded tutor + content draft generation (docs/06, docs/07).

Business logic lives here so the router stays thin. Key responsibilities:

  * RAG-lite retrieval of **approved** ``ContentItem`` bodies to ground answers
    (simple keyword + recency for the MVP — no pgvector required).
  * Guardrails: refuse to answer graded assessment questions, stay grounded in
    approved content, and always offer escalation to a teacher.
  * Persistence of every exchange as an ``AIInteraction`` and every draft as an
    ``AIGeneratedContent`` row with ``review_status`` gating (docs/07).

Cross-module models (``ContentItem``, ``LearningNode``, ...) are imported
read-only purely to retrieve grounding material; this module never writes them.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.deps import Principal, ensure_same_tenant
from app.modules.ai.client import llm_client
from app.modules.ai.models import AIGeneratedContent, AIInteraction
from app.modules.ai.schemas import DraftCreate, TutorRequest, TutorSource
from app.modules.content.models import ContentItem
from app.modules.courses.models import Course, CourseVersion, LearningNode

ESCALATION_PATH = "/teacher"

_TUTOR_SYSTEM = (
    "You are the AI tutor for The-Code Adaptive LMS. Answer the learner using ONLY the "
    "approved course material provided as grounding context. If the context does not cover the "
    "question, say so plainly and suggest escalating to a teacher rather than guessing. Never "
    "reveal answers to graded assessments. Be concise, encouraging, and Socratic where helpful."
)

_DRAFT_SYSTEM = (
    "You are a content-design assistant for The-Code Adaptive LMS. Produce a clear, "
    "well-structured draft lesson body in Markdown for the requested topic and learning "
    "objectives. The draft is a proposal for human review — it is NOT published until a "
    "designer approves it."
)

# Heuristics that flag a request for graded-assessment answers (guardrail).
_GRADED_PATTERNS = [
    re.compile(r"\banswer\s*key\b", re.I),
    re.compile(r"\b(correct|right)\s+answer(s)?\b", re.I),
    re.compile(r"\bwhat(?:'s| is| are)\s+the\s+answer", re.I),
    re.compile(
        r"\banswers?\s+(?:to|for)\s+(?:the\s+)?(quiz|exam|test|assessment|midterm|final)", re.I
    ),
    re.compile(r"\b(quiz|exam|test|assessment|midterm|final)\s+answers?\b", re.I),
    re.compile(r"\b(give|tell|show)\s+me\s+the\s+answers?\b", re.I),
    re.compile(r"\bgraded\s+(question|quiz|exam|test|assessment)\b", re.I),
]

_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "what", "why", "how", "when", "where", "which",
    "who", "this", "that", "with", "from", "into", "your", "you", "can", "does", "did", "about",
    "explain", "tell", "show", "give", "help", "please", "would", "could", "should", "have", "has",
}


@dataclass
class GroundingChunk:
    content_item_id: uuid.UUID
    node_id: uuid.UUID
    title: str
    text: str


@dataclass
class TutorOutcome:
    interaction_id: uuid.UUID
    answer: str
    grounded: bool
    refused: bool
    escalate: bool
    escalation_path: str
    sources: list[TutorSource]
    provider: str
    model: str
    stubbed: bool


# ── Guardrails / helpers ──────────────────────────────────────────────────────


def is_graded_question(question: str, *, assessment_id: uuid.UUID | None) -> bool:
    """True when the request looks like it's fishing for graded-assessment answers."""

    if assessment_id is not None:
        return True
    return any(pattern.search(question) for pattern in _GRADED_PATTERNS)


def _keywords(text: str, *, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    seen: list[str] = []
    for tok in tokens:
        if len(tok) >= 3 and tok not in _STOPWORDS and tok not in seen:
            seen.append(tok)
    return seen[:limit]


def _body_to_text(body: object, *, budget: int = 1200) -> str:
    """Flatten a JSONB content body into a bounded plain-text string."""

    parts: list[str] = []

    def walk(value: object) -> None:
        if sum(len(p) for p in parts) >= budget:
            return
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                parts.append(stripped)
        elif isinstance(value, dict):
            for val in value.values():
                walk(val)
        elif isinstance(value, list):
            for val in value:
                walk(val)

    walk(body)
    text = " ".join(parts)
    return text[:budget]


async def retrieve_grounding(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    question: str,
    node_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
    limit: int = 5,
) -> list[GroundingChunk]:
    """Retrieve approved ContentItem bodies relevant to the question.

    Tenant isolation: ``ContentItem`` is not tenant-scoped directly, so we join
    up the graph (node -> course version -> course) and filter on the course's
    ``tenant_id``. Keyword match first, then fall back to most-recent approved.
    """

    base = (
        select(ContentItem, LearningNode.title)
        .join(LearningNode, LearningNode.id == ContentItem.node_id)
        .join(CourseVersion, CourseVersion.id == LearningNode.course_version_id)
        .join(Course, Course.id == CourseVersion.course_id)
        .where(
            ContentItem.approval_status == "approved",
            ContentItem.deleted_at.is_(None),
            Course.tenant_id == tenant_id,
        )
    )
    if node_id is not None:
        base = base.where(ContentItem.node_id == node_id)
    if course_id is not None:
        base = base.where(Course.id == course_id)

    rows = []
    keywords = _keywords(question)
    if keywords:
        body_text = cast(ContentItem.body, String)
        conds = [body_text.ilike(f"%{kw}%") for kw in keywords]
        conds += [LearningNode.title.ilike(f"%{kw}%") for kw in keywords]
        kw_stmt = base.where(or_(*conds)).order_by(ContentItem.created_at.desc()).limit(limit)
        rows = (await session.execute(kw_stmt)).all()

    if not rows:
        recent = base.order_by(ContentItem.created_at.desc()).limit(limit)
        rows = (await session.execute(recent)).all()

    chunks: list[GroundingChunk] = []
    for item, node_title in rows:
        chunks.append(
            GroundingChunk(
                content_item_id=item.id,
                node_id=item.node_id,
                title=node_title or "Untitled",
                text=_body_to_text(item.body),
            )
        )
    return chunks


def _build_context(chunks: list[GroundingChunk]) -> str:
    blocks = [f"[{i + 1}] {c.title}: {c.text}" for i, c in enumerate(chunks)]
    return "\n\n".join(blocks)


def _snippet(text: str, *, length: int = 240) -> str:
    text = text.strip()
    return text if len(text) <= length else f"{text[:length].rstrip()}…"


# ── Tutor ─────────────────────────────────────────────────────────────────────


async def run_tutor(
    session: AsyncSession, principal: Principal, req: TutorRequest
) -> TutorOutcome:
    """Answer a tutor question with guardrails, then persist the interaction."""

    context_refs: dict = {
        "node_id": str(req.node_id) if req.node_id else None,
        "course_id": str(req.course_id) if req.course_id else None,
        "assessment_id": str(req.assessment_id) if req.assessment_id else None,
    }
    sources: list[TutorSource] = []

    if is_graded_question(req.question, assessment_id=req.assessment_id):
        answer = (
            "I can't help with answers to graded assessments — that would undermine your "
            "assessment. I'm happy to explain the underlying concepts or work through a similar "
            "practice example instead. If you need clarification on the assessment itself, you can "
            "escalate to your teacher."
        )
        refused, grounded, escalate = True, False, True
        provider, model, stubbed = "guardrail", "-", False
        context_refs["guardrail"] = "graded_assessment"
    else:
        chunks = await retrieve_grounding(
            session,
            tenant_id=principal.tenant_id,
            question=req.question,
            node_id=req.node_id,
            course_id=req.course_id,
        )
        grounded = bool(chunks)
        result = await llm_client.complete(
            system=_TUTOR_SYSTEM,
            user=req.question,
            context=_build_context(chunks),
            task="tutor",
        )
        answer = result.text
        provider, model, stubbed = result.provider, result.model, result.stubbed
        refused = False
        # Offer escalation whenever we couldn't ground the answer.
        escalate = not grounded
        sources = [
            TutorSource(
                content_item_id=c.content_item_id,
                node_id=c.node_id,
                title=c.title,
                snippet=_snippet(c.text),
            )
            for c in chunks
        ]
        context_refs["source_content_item_ids"] = [str(c.content_item_id) for c in chunks]

    interaction = AIInteraction(
        tenant_id=principal.tenant_id,
        user_id=principal.id,
        agent="tutor",
        context_refs=context_refs,
        messages={
            "messages": [
                {"role": "user", "content": req.question},
                {"role": "assistant", "content": answer},
            ],
            "grounded": grounded,
            "refused": refused,
            "provider": provider,
            "model": model,
            "stubbed": stubbed,
        },
    )
    session.add(interaction)
    await session.flush()

    await record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.id,
        action="ai.tutor.ask",
        object_type="ai_interaction",
        object_id=interaction.id,
        metadata={"refused": refused, "grounded": grounded, "stubbed": stubbed},
    )
    await session.commit()

    return TutorOutcome(
        interaction_id=interaction.id,
        answer=answer,
        grounded=grounded,
        refused=refused,
        escalate=escalate,
        escalation_path=ESCALATION_PATH,
        sources=sources,
        provider=provider,
        model=model,
        stubbed=stubbed,
    )


# ── Content drafts ────────────────────────────────────────────────────────────


async def generate_draft(
    session: AsyncSession, principal: Principal, req: DraftCreate
) -> AIGeneratedContent:
    """Generate an AI content draft into review (never a real ContentItem)."""

    context = ""
    grounded_ids: list[str] = []
    if req.node_id is not None:
        chunks = await retrieve_grounding(
            session,
            tenant_id=principal.tenant_id,
            question=req.topic,
            node_id=req.node_id,
        )
        context = _build_context(chunks)
        grounded_ids = [str(c.content_item_id) for c in chunks]

    prompt_lines = [f"Topic: {req.topic}", f"Modality: {req.modality}"]
    if req.objectives:
        prompt_lines.append("Learning objectives:")
        prompt_lines += [f"- {obj}" for obj in req.objectives]
    if req.instructions:
        prompt_lines.append(f"Additional instructions: {req.instructions}")
    user_prompt = "\n".join(prompt_lines)

    result = await llm_client.complete(
        system=_DRAFT_SYSTEM,
        user=user_prompt,
        context=context,
        task="draft",
    )

    interaction = AIInteraction(
        tenant_id=principal.tenant_id,
        user_id=principal.id,
        agent="content_draft",
        context_refs={
            "topic": req.topic,
            "node_id": str(req.node_id) if req.node_id else None,
            "source_content_item_ids": grounded_ids,
        },
        messages={
            "messages": [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": result.text},
            ],
            "provider": result.provider,
            "model": result.model,
            "stubbed": result.stubbed,
        },
    )
    session.add(interaction)
    await session.flush()

    draft = AIGeneratedContent(
        interaction_id=interaction.id,
        target_type="content_item",
        review_status="pending",
        draft={
            "title": req.title or req.topic,
            "modality": req.modality,
            "format": "markdown",
            "body": result.text,
            "topic": req.topic,
            "objectives": req.objectives,
            "node_id": str(req.node_id) if req.node_id else None,
            "generated_by": str(principal.id),
            "provider": result.provider,
            "model": result.model,
            "stubbed": result.stubbed,
        },
    )
    session.add(draft)
    await session.flush()

    await record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.id,
        action="ai.content.draft",
        object_type="ai_generated_content",
        object_id=draft.id,
        metadata={"topic": req.topic, "stubbed": result.stubbed},
    )
    await session.commit()
    await session.refresh(draft)
    return draft


async def list_drafts(
    session: AsyncSession,
    principal: Principal,
    *,
    review_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AIGeneratedContent], int]:
    """List drafts for the caller's tenant (scoped via the linked interaction)."""

    base = (
        select(AIGeneratedContent)
        .join(AIInteraction, AIInteraction.id == AIGeneratedContent.interaction_id)
        .where(AIInteraction.tenant_id == principal.tenant_id)
    )
    if review_status:
        base = base.where(AIGeneratedContent.review_status == review_status)

    count_stmt = (
        select(func.count())
        .select_from(AIGeneratedContent)
        .join(AIInteraction, AIInteraction.id == AIGeneratedContent.interaction_id)
        .where(AIInteraction.tenant_id == principal.tenant_id)
    )
    if review_status:
        count_stmt = count_stmt.where(AIGeneratedContent.review_status == review_status)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        await session.execute(
            base.order_by(AIGeneratedContent.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), total


async def _load_draft_for_tenant(
    session: AsyncSession, principal: Principal, draft_id: uuid.UUID
) -> AIGeneratedContent | None:
    """Load a draft and enforce tenant isolation via its linked interaction."""

    draft = await session.get(AIGeneratedContent, draft_id)
    if draft is None:
        return None
    interaction = (
        await session.get(AIInteraction, draft.interaction_id)
        if draft.interaction_id
        else None
    )
    if interaction is None:
        return None
    ensure_same_tenant(principal, interaction.tenant_id)
    return draft


async def approve_draft(
    session: AsyncSession, principal: Principal, draft_id: uuid.UUID
) -> AIGeneratedContent | None:
    """Mark a draft approved.

    TODO(content module): promotion of an approved draft into a real, versioned
    ``ContentItem`` (with ``approval_status``) is owned by the content module —
    this endpoint only flips review state and emits an audit event for handoff.
    """

    draft = await _load_draft_for_tenant(session, principal, draft_id)
    if draft is None:
        return None

    draft.review_status = "approved"
    await session.flush()
    await record_audit(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.id,
        action="ai.content.approve",
        object_type="ai_generated_content",
        object_id=draft.id,
        metadata={"review_status": "approved"},
    )
    await session.commit()
    await session.refresh(draft)
    return draft
