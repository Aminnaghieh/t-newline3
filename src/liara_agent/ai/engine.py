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

# Schema hint appended to the RCA system prompt to force the model to emit
# the exact keys expected by ``Diagnosis`` / ``Hypothesis``.
_RCA_SCHEMA_HINT = """

You MUST return a single JSON object with EXACTLY this structure:

{
  "root_cause_summary": "<one-paragraph summary of the most likely root cause>",
  "confidence": <float between 0.0 and 1.0>,
  "hypotheses": [
    {
      "title": "<short human-readable title>",
      "probability": <float between 0.0 and 1.0>,
      "category": "<one of: resource_exhaustion | config_error | code_bug | network_issue | unknown>",
      "explanation": "<why this hypothesis is plausible>",
      "impact": "<what this causes for the user/system>"
    }
  ],
  "suggested_remediations": [
    {
      "id": "<short snake_case id>",
      "title": "<short human-readable title>",
      "action_type": "<one of: restart | resize | scale | env_fix | code_patch>",
      "description": "<what the action does>",
      "risk_level": "<low | medium | high | critical>",
      "auto_executable": <true|false>,
      "parameters": { }
    }
  ]
}

Rules:
- Always include at least one hypothesis.
- ``confidence`` and every ``probability`` MUST be a float in [0, 1] (NOT a percentage).
- Every hypothesis MUST contain title, probability, category, explanation, and impact.
- Do NOT wrap the JSON in markdown code fences.
- Do NOT add any keys outside the schema above.
"""


class AIEngine:
    """Async AI Engine wrapping OpenAI for SRE analysis and decision-making."""

    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://ai.liara.ir/api/6ada21b27508e6ca2f0acf7f/v1",
        ) if api_key else None

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
            {"role": "system", "content": RCA_SYSTEM_PROMPT + _RCA_SCHEMA_HINT},
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
            data = json.loads(content)
            return self._ensure_rca_shape(data, context)
        except Exception as e:
            logger.error("AI troubleshooting failed: %s", e)
            return {}

    def _ensure_rca_shape(
        self, data: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Post-process the model output so it matches ``Diagnosis``.

        Adds missing keys with sensible defaults derived from ``context`` so
        that the caller never has to fall back to heuristics just because the
        model omitted a field.
        """
        if not isinstance(data, dict):
            data = {}

        project = context.get("project_name", "the project")
        status = context.get("status", "unknown")

        # --- root cause summary ---
        if not data.get("root_cause_summary"):
            data["root_cause_summary"] = str(
                data.get("summary")
                or data.get("root_cause")
                or data.get("description")
                or f"وضعیت '{status}' برای پروژه '{project}' نیاز به بررسی دارد."
            )

        # --- confidence ---
        conf = data.get("confidence", data.get("probability", 0.5))
        try:
            conf_f = float(conf)
            if conf_f > 1.0:
                conf_f /= 100.0
        except (TypeError, ValueError):
            conf_f = 0.5
        data["confidence"] = max(0.0, min(1.0, conf_f))

        # --- hypotheses ---
        hyps = data.get("hypotheses") or data.get("causes") or []
        if not isinstance(hyps, list) or not hyps:
            hyps = [{
                "title": "بررسی دستی وضعیت سرویس",
                "probability": 0.5,
                "category": "unknown",
                "explanation": f"داده کافی برای تحلیل خودکار موجود نیست. وضعیت فعلی: {status}.",
                "impact": "نیاز به بررسی دستی توسط تیم عملیات",
            }]
        normalized_hyps: list[dict[str, Any]] = []
        for idx, h in enumerate(hyps, start=1):
            if not isinstance(h, dict):
                continue
            prob = h.get("probability", h.get("confidence", 0.5))
            try:
                prob_f = float(prob)
                if prob_f > 1.0:
                    prob_f /= 100.0
            except (TypeError, ValueError):
                prob_f = 0.5
            normalized_hyps.append({
                "title": str(
                    h.get("title")
                    or h.get("name")
                    or h.get("cause")
                    or f"فرضیه {idx}"
                ),
                "probability": max(0.0, min(1.0, prob_f)),
                "category": str(h.get("category") or "unknown"),
                "explanation": str(
                    h.get("explanation")
                    or h.get("description")
                    or h.get("details")
                    or "توضیحاتی ارائه نشده است."
                ),
                "impact": str(
                    h.get("impact")
                    or h.get("effect")
                    or h.get("consequence")
                    or "اثر نامشخص"
                ),
            })
        data["hypotheses"] = normalized_hyps

        # --- remediations ---
        rems = data.get("suggested_remediations") or data.get("remediations") or []
        if not isinstance(rems, list):
            rems = []
        normalized_rems: list[dict[str, Any]] = []
        for idx, r in enumerate(rems, start=1):
            if not isinstance(r, dict):
                continue
            normalized_rems.append({
                "id": str(r.get("id") or f"fix_{idx}"),
                "title": str(r.get("title") or r.get("name") or f"راهکار {idx}"),
                "action_type": str(r.get("action_type") or r.get("action") or "restart"),
                "description": str(r.get("description") or r.get("details") or ""),
                "risk_level": str(r.get("risk_level") or "medium"),
                "auto_executable": bool(r.get("auto_executable", True)),
                "parameters": r.get("parameters") or {},
            })
        data["suggested_remediations"] = normalized_rems

        return data

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