from __future__ import annotations

import json
from typing import Any

from sre_agent.agent.prompts import SYSTEM_PROMPT, user_prompt
from sre_agent.agent.schema import DiagnosisReport
from sre_agent.config import Settings
from sre_agent.llm.client import LLMClient
from sre_agent.obs.trace import Tracer
from sre_agent.safety.allowlist import ToolCatalog
from sre_agent.tools.ssh_exec import SSHExecutor


def tools_for_openai(catalog: ToolCatalog) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, tool in catalog.tools.items():
        props: dict[str, Any] = {}
        required: list[str] = []
        if tool.path_arg:
            props["path"] = {
                "type": "string",
                "enum": sorted(catalog.allowed_paths),
                "description": "Path argument; must be allowlisted",
            }
            required.append("path")
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            }
        )
    # finalization tool-less: model returns JSON content
    return out


class AgentLoop:
    def __init__(
        self,
        settings: Settings,
        catalog: ToolCatalog,
        executor: SSHExecutor,
        llm: LLMClient,
        tracer: Tracer,
    ) -> None:
        self.settings = settings
        self.catalog = catalog
        self.executor = executor
        self.llm = llm
        self.tracer = tracer

    async def run(self, host_id: str, symptom: str) -> DiagnosisReport:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(host_id, symptom)},
        ]
        tools = tools_for_openai(self.catalog)
        self.tracer.log("diagnose_start", host_id=host_id, symptom=symptom)

        for step in range(self.settings.max_agent_steps):
            msg = await self.llm.chat(messages, tools=tools)
            self.tracer.log("llm_message", step=step, message=msg)
            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content")

            if tool_calls:
                messages.append(msg)
                for call in tool_calls:
                    fn = call["function"]
                    name = fn["name"]
                    raw_args = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    path = args.get("path")
                    try:
                        result = await self.executor.run_tool(host_id, name, path=path)
                        payload = {
                            "ok": True,
                            "exit_status": result.exit_status,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "command": result.command,
                        }
                    except Exception as exc:  # noqa: BLE001 - surface to model
                        payload = {"ok": False, "error": str(exc)}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(payload, ensure_ascii=False),
                        }
                    )
                continue

            if content:
                try:
                    report = DiagnosisReport.from_llm_json(content)
                except Exception:
                    # Ask once more for valid JSON
                    messages.append(msg)
                    messages.append(
                        {
                            "role": "user",
                            "content": "Invalid JSON. Reply with ONLY the diagnosis JSON object.",
                        }
                    )
                    continue
                self.tracer.log("diagnose_end", report=report.model_dump())
                return report

            messages.append(
                {
                    "role": "user",
                    "content": "Please either call a tool or return the final JSON report.",
                }
            )

        raise RuntimeError(f"agent exceeded max steps ({self.settings.max_agent_steps})")
