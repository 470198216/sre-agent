from __future__ import annotations

from sre_agent.config import load_tools_config
from sre_agent.safety.allowlist import ToolCatalog, build_catalog


def get_catalog() -> ToolCatalog:
    return build_catalog(load_tools_config())
