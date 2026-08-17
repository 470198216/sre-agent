from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncssh

from sre_agent.config import Settings, load_hosts
from sre_agent.obs.trace import Tracer
from sre_agent.safety.allowlist import ToolCatalog, render_command
from sre_agent.safety.approval import ApprovalGate
from sre_agent.safety.sanitize import redact, truncate


@dataclass
class ExecResult:
    host_id: str
    tool: str
    command: str
    exit_status: int | None
    stdout: str
    stderr: str


class SSHExecutor:
    """Execute allowlisted commands on a remote host over SSH."""

    def __init__(
        self,
        settings: Settings,
        catalog: ToolCatalog,
        tracer: Tracer | None = None,
    ) -> None:
        self.settings = settings
        self.catalog = catalog
        self.tracer = tracer
        raw = load_hosts()
        self.hosts: dict[str, Any] = dict(raw.get("hosts") or {})
        # Allow bastion entries defined at YAML root alongside "hosts"
        for k, v in raw.items():
            if k != "hosts" and isinstance(v, dict) and "host" in v and "user" in v:
                self.hosts.setdefault(k, v)
        self.gate = ApprovalGate()

    def _host_conf(self, host_id: str) -> dict[str, Any]:
        if host_id not in self.hosts:
            raise KeyError(f"unknown host id: {host_id}. Add it to configs/hosts.yaml")
        return dict(self.hosts[host_id])

    def _client_keys(self) -> list[str]:
        key_path = self.settings.ssh_private_key_path
        if not key_path:
            raise RuntimeError("SSH_PRIVATE_KEY_PATH is empty; set it in .env")
        path = Path(key_path)
        if not path.exists():
            raise FileNotFoundError(f"SSH private key not found: {path}")
        return [str(path)]

    async def _connect(self, host_id: str):
        conf = self._host_conf(host_id)
        client_keys = self._client_keys()
        jump = conf.get("jump")
        if not jump:
            return await asyncssh.connect(
                conf["host"],
                port=int(conf.get("port", 22)),
                username=conf["user"],
                client_keys=client_keys,
                passphrase=self.settings.ssh_passphrase,
                known_hosts=None,
            )

        jump_conf = self._host_conf(jump)
        tunnel = await asyncssh.connect(
            jump_conf["host"],
            port=int(jump_conf.get("port", 22)),
            username=jump_conf["user"],
            client_keys=client_keys,
            passphrase=self.settings.ssh_passphrase,
            known_hosts=None,
        )
        try:
            conn = await asyncssh.connect(
                conf["host"],
                port=int(conf.get("port", 22)),
                username=conf["user"],
                client_keys=client_keys,
                passphrase=self.settings.ssh_passphrase,
                known_hosts=None,
                tunnel=tunnel,
            )
        except Exception:
            tunnel.close()
            await tunnel.wait_closed()
            raise

        # Keep tunnel alive by attaching to connection object
        conn._sre_tunnel = tunnel  # type: ignore[attr-defined]
        return conn

    async def _close(self, conn) -> None:
        tunnel = getattr(conn, "_sre_tunnel", None)
        conn.close()
        await conn.wait_closed()
        if tunnel is not None:
            tunnel.close()
            await tunnel.wait_closed()

    async def run_tool(self, host_id: str, tool_name: str, path: str | None = None) -> ExecResult:
        tool = self.catalog.get(tool_name)
        self.gate.require(tool.name, tool.needs_approval)
        command = render_command(tool, path, self.catalog.allowed_paths)

        if self.tracer:
            self.tracer.log("tool_start", host_id=host_id, tool=tool_name, command=command)

        conn = await self._connect(host_id)
        try:
            result = await conn.run(
                command,
                check=False,
                timeout=self.catalog.timeout_sec,
            )
            stdout = redact(truncate(result.stdout or "", self.catalog.max_output_bytes))
            stderr = redact(truncate(result.stderr or "", self.catalog.max_output_bytes))
            exec_result = ExecResult(
                host_id=host_id,
                tool=tool_name,
                command=command,
                exit_status=result.exit_status,
                stdout=stdout,
                stderr=stderr,
            )
        finally:
            await self._close(conn)

        if self.tracer:
            self.tracer.log(
                "tool_end",
                host_id=host_id,
                tool=tool_name,
                exit_status=exec_result.exit_status,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
            )
        return exec_result

    async def ping(self, host_id: str) -> str:
        conf = self._host_conf(host_id)
        conn = await self._connect(host_id)
        try:
            result = await conn.run("echo ok && hostname && whoami", check=False, timeout=15)
            body = (result.stdout or "").strip()
            return body or f"connected to {conf['host']}"
        finally:
            await self._close(conn)
