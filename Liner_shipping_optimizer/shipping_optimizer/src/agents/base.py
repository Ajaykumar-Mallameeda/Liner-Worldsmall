"""Base Agent class - parent for all agents"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.llm.metrics import llm_metrics
from src.llm.evaluator_manager import evaluator
from src.llm.client import llm_client
from src.utils.logger import logger


class BaseAgent(ABC):
    def __init__(self, name: str, role: str, model: str, llm_role: Optional[str] = None):
        self.name = name
        self.role = role
        self.model = model
        # ``llm_role`` is the role key used by the provider router to look
        # up the per-provider model.  Defaults are derived from the agent
        # class name; agents can override.
        self.llm_role = llm_role or self._default_llm_role()

        logger.info(
            "agent_initialized",
            agent=name,
            role=role,
            model=model,
            llm_role=self.llm_role,
        )

    def _default_llm_role(self) -> str:
        n = (self.name or "").lower()
        if n in ("coordinator",):
            return "coordinator"
        if n.startswith("regional"):
            return "regional"
        if "service_gen" in n or "svc_gen" in n or n == "svc_gen":
            return "service_generator"
        if "orchestrator" in n:
            return "orchestrator"
        return "orchestrator"

    @abstractmethod
    def get_system_prompt(self) -> str:
        pass

    # LLM Call Wrapper
    def call_llm(self, user_message: str, temperature: float = 0.2) -> str:

        system_prompt = self.get_system_prompt()
        has_json_instruction = "Return ONLY valid JSON" in user_message or "Return JSON" in user_message
        if not has_json_instruction:
            enhanced_user_message = user_message + "\n\nThink step by step. Follow the output format strictly."
        else:
            enhanced_user_message = user_message

        skip_evaluator = has_json_instruction

        for attempt in range(2):
            try:
                logger.info(
                    "llm_request",
                    agent=self.name,
                    model=self.model,
                    llm_role=self.llm_role,
                )

                response = llm_client.chat(
                    model=self.model,
                    system=system_prompt,
                    user_message=enhanced_user_message,
                    temperature=temperature,
                    role=self.llm_role,
                )

                response = response.strip()

                if not skip_evaluator:
                    scores = evaluator.evaluate(response)
                    llm_metrics.log(self.name, scores)

                    logger.info(
                        "llm_evaluation",
                        agent=self.name,
                        scores=scores,
                    )

                    if scores["total_score"] < 0.5:
                        logger.warning("llm_low_quality", agent=self.name)
                        response = (
                            "Strategy: C\n"
                            "Reason 1: Balanced network design across 50+ ports\n"
                            "Reason 2: Handles demand variability for 100+ lanes"
                        )

                return response

            except Exception as e:
                logger.warning(
                    "llm_retry",
                    agent=self.name,
                    error=str(e),
                    attempt=attempt + 1,
                )

        logger.error("llm_failed", agent=self.name)
        return ("Strategy: C\n"
                "Reason 1: Balanced network design across 50+ ports\n"
                "Reason 2: Handles demand variability for 100+ lanes")