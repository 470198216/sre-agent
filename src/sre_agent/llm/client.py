from __future__ import annotations

import json
from typing import Any

import httpx

from sre_agent.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is empty; set it in .env")

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.1,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.ConnectError as exc:
                hint = (
                    f"无法连接 LLM: {url}\n{exc}\n"
                    "SSL WRONG_VERSION_NUMBER 通常是协议对不上："
                    "LLM_BASE_URL 写了 https:// 但对方端口其实是 http "
                    "（本地中转常见），或直连 api.openai.com 被拦截。"
                    "国内请改用 OpenAI 兼容网关；本地服务多用 http://127.0.0.1:<端口>/v1。"
                    "改 .env 后重新跑 diagnose。SSH ping/tool 不走这条路径。"
                )
                raise RuntimeError(hint) from exc
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]
