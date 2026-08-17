from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer

from sre_agent.agent.loop import AgentLoop
from sre_agent.config import Settings
from sre_agent.llm.client import LLMClient
from sre_agent.obs.trace import Tracer
from sre_agent.tools.catalog import get_catalog
from sre_agent.tools.ssh_exec import SSHExecutor

app = typer.Typer(add_completion=False, no_args_is_help=True, help="SSH-based SRE diagnostic agent")


def _settings() -> Settings:
    return Settings()


@app.command("ping")
def ping(host: str = typer.Option(..., "--host", help="Host id in configs/hosts.yaml")) -> None:
    """Test SSH connectivity to a configured remote host."""

    async def _run() -> None:
        settings = _settings()
        catalog = get_catalog()
        executor = SSHExecutor(settings, catalog)
        out = await executor.ping(host)
        typer.echo(out)

    asyncio.run(_run())


@app.command("tool")
def tool(
    host: str = typer.Option(..., "--host"),
    name: str = typer.Option(..., "--name", help="Allowlisted tool name"),
    path: Optional[str] = typer.Option(None, "--path", help="Path arg for tools like du_top"),
) -> None:
    """Run one allowlisted tool on the remote host (no LLM)."""

    async def _run() -> None:
        settings = _settings()
        catalog = get_catalog()
        tracer = Tracer()
        executor = SSHExecutor(settings, catalog, tracer=tracer)
        result = await executor.run_tool(host, name, path=path)
        typer.echo(f"command: {result.command}")
        typer.echo(f"exit: {result.exit_status}")
        if result.stdout:
            typer.echo("--- stdout ---")
            typer.echo(result.stdout)
        if result.stderr:
            typer.echo("--- stderr ---")
            typer.echo(result.stderr)
        typer.echo(f"trace: {tracer.path}")

    asyncio.run(_run())


@app.command("diagnose")
def diagnose(
    host: str = typer.Option(..., "--host"),
    symptom: str = typer.Option(..., "--symptom", help="Alert text or symptom description"),
) -> None:
    """Run the full LLM + SSH tool diagnostic loop."""

    async def _run() -> None:
        settings = _settings()
        catalog = get_catalog()
        tracer = Tracer()
        executor = SSHExecutor(settings, catalog, tracer=tracer)
        llm = LLMClient(settings)
        agent = AgentLoop(settings, catalog, executor, llm, tracer)
        report = await agent.run(host, symptom)
        typer.echo(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
        typer.echo(f"trace: {tracer.path}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
