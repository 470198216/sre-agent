from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    tool: str
    summary: str


class RecommendedAction(BaseModel):
    action: str
    risk: str = "low"
    needs_approval: bool = True


class DiagnosisReport(BaseModel):
    symptom: str
    hypotheses: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    root_cause: str = ""
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)
    kernel_hint: str | None = None

    @classmethod
    def from_llm_json(cls, text: str) -> "DiagnosisReport":
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)
        data: dict[str, Any] = json.loads(text)
        return cls.model_validate(data)
