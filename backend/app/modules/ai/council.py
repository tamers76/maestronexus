"""LLM Council engine (ported in spirit from DeepT's ``council.service.ts``).

Two execution modes:

* **single** — one model answers directly (fast path).
* **council** — several *member* models answer the same task in parallel, then a
  *chairman* model synthesizes one final answer.

This module is pure execution: it takes a fully-resolved config and talks to the
shared :data:`app.modules.ai.client.llm_client`. Resolution of *which* models /
prompts / keys to use (from tenant ``AiSettings`` → env → stage defaults) lives
in ``app.modules.integrations.service`` so this stays DB-free and reusable.

Graceful degradation matches the rest of the AI layer: failed members are
dropped; if every member fails the chairman falls back to single execution; and
with no API key the deterministic offline stub is used throughout.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.modules.ai.client import llm_client

logger = logging.getLogger(__name__)


@dataclass
class MemberResponse:
    model: str
    text: str | None
    stubbed: bool
    error: str | None = None


@dataclass
class CouncilResult:
    """Outcome of a single- or council-mode execution."""

    text: str
    mode: str
    provider: str
    chairman_model: str
    members: list[MemberResponse] = field(default_factory=list)
    stubbed: bool = False

    def transcript(self) -> dict:
        """JSONB-friendly transcript for persistence on the StageRun."""

        return {
            "mode": self.mode,
            "chairman_model": self.chairman_model,
            "members": [
                {"model": m.model, "text": m.text, "stubbed": m.stubbed, "error": m.error}
                for m in self.members
            ],
        }


async def run_single(
    *,
    system: str,
    user: str,
    context: str = "",
    model: str,
    provider_key: str = "openai",
    api_key: str | None = None,
    base_url: str | None = None,
    task: str = "stage",
) -> CouncilResult:
    """Execute a task with a single model."""

    result = await llm_client.complete(
        system=system,
        user=user,
        context=context,
        task=task,
        provider_key=provider_key,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
    return CouncilResult(
        text=result.text,
        mode="single",
        provider=result.provider,
        chairman_model=result.model,
        members=[MemberResponse(model=result.model, text=result.text, stubbed=result.stubbed)],
        stubbed=result.stubbed,
    )


def _build_chairman_user(user: str, members: list[MemberResponse]) -> str:
    successful = [m for m in members if m.text]
    blocks = [
        f"--- Response from Model {i + 1} ({m.model}) ---\n{m.text}"
        for i, m in enumerate(successful)
    ]
    return (
        "ORIGINAL TASK:\n"
        f"{user}\n\n"
        f"COUNCIL MEMBER RESPONSES ({len(successful)} responses):\n\n"
        + "\n\n".join(blocks)
        + "\n\n---\n\nSynthesize these into ONE final answer that combines the best "
        "elements from each, following the same structure the members used."
    )


async def run_council(
    *,
    user: str,
    context: str = "",
    members: list[str],
    chairman: str,
    member_system_prompt: str,
    chairman_system_prompt: str,
    provider_key: str = "openai",
    api_key: str | None = None,
    base_url: str | None = None,
    task: str = "stage",
) -> CouncilResult:
    """Execute a task across member models, then synthesize with the chairman."""

    if not members:
        # No members configured -> behave like single using the chairman model.
        return await run_single(
            system=member_system_prompt,
            user=user,
            context=context,
            model=chairman,
            provider_key=provider_key,
            api_key=api_key,
            base_url=base_url,
            task=task,
        )

    async def _one(model: str) -> MemberResponse:
        try:
            r = await llm_client.complete(
                system=member_system_prompt,
                user=user,
                context=context,
                task=task,
                provider_key=provider_key,
                model=model,
                api_key=api_key,
                base_url=base_url,
            )
            return MemberResponse(model=model, text=r.text, stubbed=r.stubbed)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Council member %s failed: %s", model, exc)
            return MemberResponse(model=model, text=None, stubbed=False, error=str(exc))

    member_results = await asyncio.gather(*[_one(m) for m in members])
    successful = [m for m in member_results if m.text]

    if not successful:
        logger.warning("All council members failed; falling back to single (chairman)")
        single = await run_single(
            system=member_system_prompt,
            user=user,
            context=context,
            model=chairman,
            provider_key=provider_key,
            api_key=api_key,
            base_url=base_url,
            task=task,
        )
        single.mode = "council"
        single.members = list(member_results)
        return single

    if len(successful) == 1:
        only = successful[0]
        return CouncilResult(
            text=only.text or "",
            mode="council",
            provider=provider_key,
            chairman_model=only.model,
            members=list(member_results),
            stubbed=only.stubbed,
        )

    chairman_result = await llm_client.complete(
        system=chairman_system_prompt,
        user=_build_chairman_user(user, member_results),
        context="",
        task=task,
        provider_key=provider_key,
        model=chairman,
        api_key=api_key,
        base_url=base_url,
    )
    return CouncilResult(
        text=chairman_result.text,
        mode="council",
        provider=chairman_result.provider,
        chairman_model=chairman_result.model,
        members=list(member_results),
        stubbed=chairman_result.stubbed or all(m.stubbed for m in successful),
    )


__all__ = ["MemberResponse", "CouncilResult", "run_single", "run_council"]
