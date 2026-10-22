"""AI Engine for intelligent SRE reasoning, project analysis, and troubleshooting."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from liara_agent.ai.prompts.advisor import (
    DEPLOYMENT_ADVISOR_PROMPT,
    OPTIMIZATION_PROMPT,
    SCALING_ADVISOR_PROMPT,
)
from liara_agent.ai.prompts.analyzer import (
    PLAN_RECOMMENDATION_PROMPT,
    PROJECT_ANALYSIS_PROMPT,
)
from liara_agent.ai.prompts.debugger import (
    RCA_SYSTEM_PROMPT,
    REMEDIATION_PROMPT,
    VERIFICATION_PROMPT,
)
from liara_agent.ai.tools import LIARA_TOOLS

logger = logging.getLogger(__name__)


class AIEngine:
    """Async AI Engine wrapping OpenAI for SRE analysis and decision-making."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None

    async def analyze_project(self, project_info: dict[str, Any]) -> dict[str, Any]:
        """Analyze project files and provide configuration recommendations."""
        if not self.client:
            return {"note": "AI key not configured; using rule-based analysis."}

        messages = [
            {"role": "system", "content": PROJECT_ANALYSIS_PROMPT},
            {"role": "user", "content": f"Project structure details:\n```json\n{json.dumps(project_info, ensure_ascii=False)}\n```"},
        ]
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            logger.error("AI project analysis failed: %s", e)
            return {"error": str(e)}

    async def troubleshoot(self, context: dict[str, Any]) -> dict[str, Any]:
        """Perform Root Cause Analysis (RCA) and generate hypotheses and fixes."""
        if not self.client:
            return {}

        messages = [
            {"role": "system", "content": RCA_SYSTEM_PROMPT},
            {"role": "user", "content": f"Runtime context for troubleshooting:\n```json\n{json.dumps(context, ensure_ascii=False)}\n```"},
        ]
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            logger.error("AI troubleshooting failed: %s", e)
            return {}

    async def recommend_plan(self, project_analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate AI-powered plan recommendation."""
        if not self.client:
            return {}

        messages = [
            {"role": "system", "content": PLAN_RECOMMENDATION_PROMPT},
            {"role": "user", "content": f"Project analysis:\n```json\n{json.dumps(project_analysis, ensure_ascii=False)}\n```"},
        ]
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            logger.error("AI plan recommendation failed: %s", e)
            return {}

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools_enabled: bool = True,
    ) -> tuple[str | None, list[Any]]:
        """General multi-turn chat with optional tool calling."""
        if not self.client:
            return "کلید OpenAI تنظیم نشده است. از 'liara-agent config set-openai-key' استفاده کنید.", []

        tools_param = [
            {"type": t["type"], "function": t["function"]}
            for t in LIARA_TOOLS
        ] if tools_enabled else None

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools_param,
                temperature=0.3,
            )
            msg = resp.choices[0].message
            return msg.content, msg.tool_calls or []
        except Exception as e:
            return f"خطا در ارتباط با هوش مصنوعی: {e}", []
