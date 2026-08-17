from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApprovalGate:
    """v0: write tools are not shipped; keep hook for later."""

    def require(self, tool_name: str, needs_approval: bool) -> None:
        if needs_approval:
            raise PermissionError(
                f"tool {tool_name} requires human approval; not auto-executed in v0"
            )
