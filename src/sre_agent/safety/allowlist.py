from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Applied to the interpolated path only. Templates in tools.yaml are trusted
# and may contain `2>/dev/null`, pipes, and `||`.
_PATH_FORBIDDEN = (">", ">>", "$(", "`", "\n", ";", "&&", "|")

# Destructive verbs: still scan the final command in case YAML is edited badly.
_COMMAND_FORBIDDEN = (
    "rm ",
    "mkfs",
    "dd ",
    "reboot",
    "shutdown",
    "poweroff",
    "userdel",
    "passwd",
    "chmod 777",
    "$(",
    "`",
    "\n",
    ";",
)


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    command: str
    needs_approval: bool = False
    path_arg: bool = False


@dataclass(frozen=True)
class ToolCatalog:
    tools: dict[str, ToolDef]
    timeout_sec: int
    max_output_bytes: int
    allowed_paths: set[str]

    def get(self, name: str) -> ToolDef:
        if name not in self.tools:
            raise KeyError(f"tool not allowlisted: {name}")
        return self.tools[name]


def build_catalog(cfg: dict[str, Any]) -> ToolCatalog:
    defaults = cfg.get("defaults") or {}
    tools_raw = cfg.get("tools") or {}
    tools: dict[str, ToolDef] = {}
    for name, spec in tools_raw.items():
        tools[name] = ToolDef(
            name=name,
            description=str(spec.get("description") or name),
            command=str(spec["command"]),
            needs_approval=bool(spec.get("needs_approval", False)),
            path_arg=bool(spec.get("path_arg", False)),
        )
    return ToolCatalog(
        tools=tools,
        timeout_sec=int(defaults.get("timeout_sec", 20)),
        max_output_bytes=int(defaults.get("max_output_bytes", 65536)),
        allowed_paths=set(defaults.get("allowed_paths") or ["/"]),
    )


def render_command(tool: ToolDef, path: str | None, allowed_paths: set[str]) -> str:
    if tool.path_arg:
        if not path:
            raise ValueError(f"tool {tool.name} requires path")
        if path not in allowed_paths:
            raise ValueError(f"path not allowed: {path}")
        for bad in _PATH_FORBIDDEN:
            if bad in path:
                raise ValueError(f"forbidden token {bad!r} in path")
        command = tool.command.format(path=path)
    else:
        if path:
            raise ValueError(f"tool {tool.name} does not accept path")
        command = tool.command

    lowered = command.lower()
    for bad in _COMMAND_FORBIDDEN:
        if bad in lowered:
            raise ValueError(f"forbidden token {bad!r} in command")
    return command
