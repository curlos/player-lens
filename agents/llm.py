"""The model client: one Microsoft Agent Framework ``Agent`` per pipeline role on a Foundry-hosted model.

``LLM.complete`` sends one JSON payload to one agent and returns its JSON answer. It enforces the 20 s timeout,
checks the spend gate before the call and records the exact token usage in the ledger after it (app/budget.py).
Tests use a fake with the same ``complete`` signature, so no test ever reaches Azure.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Protocol

from agents import config as C
from app.budget import Budget
from app.settings import Settings

PROMPTS = Path(__file__).with_name("prompts")


class LLMError(Exception):
    """A call failed or answered something that is not the JSON the agent was asked for."""


class LLM(Protocol):
    async def complete(self, agent: str, payload: dict[str, Any], *, key: str) -> dict[str, Any]: ...


def parse_json(text: str) -> dict[str, Any]:
    """The first JSON object in a model answer (models sometimes wrap it in a code fence)."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("the answer contains no JSON object")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as err:
        raise LLMError(f"invalid JSON: {err}") from err
    if not isinstance(value, dict):
        raise LLMError("the JSON answer is not an object")
    return value


class FoundryLLM:
    """Agent Framework agents (one per role, instructions from ``agents/prompts/<role>.md``) on the Foundry deployment."""

    def __init__(self, settings: Settings, budget: Budget):
        from agent_framework import Agent  # imported here so tests and template-only runs never need a model
        from agent_framework.openai import OpenAIChatCompletionClient

        self.budget = budget
        client = OpenAIChatCompletionClient(model=settings.openai_deployment, api_key=settings.openai_api_key, base_url=settings.llm_base_url)
        self.agents = {
            name: Agent(client, instructions=(PROMPTS / f"{name}.md").read_text(encoding="utf-8"), name=name) for name in C.AGENT_NAMES
        }
        self._slots = asyncio.Semaphore(C.LLM_MAX_CONCURRENT)

    async def complete(self, agent: str, payload: dict[str, Any], *, key: str) -> dict[str, Any]:
        options = {"temperature": C.TEMPERATURE[agent], "max_tokens": C.LLM_MAX_OUTPUT_TOKENS, "response_format": {"type": "json_object"}}
        try:
            async with self._slots:
                self.budget.check_llm()  # after the wait for a slot, so queued calls see the latest spend (BudgetExceeded -> templates)
                response = await asyncio.wait_for(
                    self.agents[agent].run(json.dumps(payload, ensure_ascii=False), options=options), timeout=C.LLM_TIMEOUT_S
                )
        except asyncio.TimeoutError as err:
            raise LLMError(f"{agent} timed out after {C.LLM_TIMEOUT_S} s") from err
        except Exception as err:  # the SDK raises its own types; the pipeline only needs to know it failed
            raise LLMError(f"{agent} call failed: {type(err).__name__}") from err
        usage = response.usage_details or {}
        self.budget.record_llm(f"{key}:{agent}", int(usage.get("input_token_count") or 0), int(usage.get("output_token_count") or 0))
        return parse_json(response.text)
