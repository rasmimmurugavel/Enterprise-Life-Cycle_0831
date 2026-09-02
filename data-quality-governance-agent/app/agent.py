"""Claude agent engine: ReAct loop over the Data Quality & Governance
MCP server (FR-121, HLD §2.2).

This module owns exactly two things:
  1. Discovering the MCP server's tools and translating them into
     Anthropic tool-use definitions - the tool CONTRACT lives only in
     mcp_server/server.py; this file never hand-maintains a second copy.
  2. Running the bounded send -> tool_use -> tool_result -> send loop
     and validating the final answer against the findings JSON shape.

`app/app.py` (Streamlit) calls the synchronous wrappers at the bottom
of this file; everything else is async because the MCP SDK is async.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import jsonschema
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings
from app.prompts import SCHEMA_INSPECTION_SYSTEM_PROMPT, SYSTEM_PROMPT

_FINDINGS_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "eval" / "schemas" / "findings.schema.json"
_findings_schema_cache: dict[str, Any] | None = None


class AgentRunError(Exception):
    """Raised when a run cannot produce a valid, schema-conforming result."""


def _load_findings_schema() -> dict[str, Any]:
    global _findings_schema_cache
    if _findings_schema_cache is None:
        with open(_FINDINGS_SCHEMA_PATH, encoding="utf-8") as fh:
            _findings_schema_cache = json.load(fh)
    return _findings_schema_cache


def validate_findings(findings: dict[str, Any]) -> None:
    """HLD §2.2 / §6: fail closed. A findings payload that doesn't match
    eval/schemas/findings.schema.json is never handed to the UI or the
    eval scorer as if it were trustworthy - the run is a failure."""
    schema = _load_findings_schema()
    try:
        jsonschema.validate(instance=findings, schema=schema)
    except jsonschema.ValidationError as exc:
        raise AgentRunError(
            f"Agent's final answer did not match the findings schema: {exc.message} "
            f"(path: {'/'.join(str(p) for p in exc.absolute_path) or '(root)'})"
        ) from exc


@dataclass
class ToolCallEvent:
    """One tool call the agent made, for the UI's live progress view (NFR-209)."""

    tool_name: str
    arguments: dict[str, Any]
    result_summary: str
    is_error: bool = False


@dataclass
class AuditRunResult:
    run_id: str
    findings: dict[str, Any]
    tool_calls: list[ToolCallEvent] = field(default_factory=list)
    stopped_reason: str = "completed"  # or "max_tool_calls_reached"


ProgressCallback = Callable[[ToolCallEvent], None]


@asynccontextmanager
async def _mcp_session() -> AsyncIterator[ClientSession]:
    command, *args = settings.mcp_server_command
    # The MCP SDK does NOT inherit the parent process's environment by
    # default (mcp.client.stdio.get_default_environment() only passes
    # through a safe subset like PATH/HOME) - without this, the server
    # subprocess would silently fall back to config.py's defaults and
    # never see PGHOST/PGPASSWORD/DATABASE_URL/DQ_* from .env, which
    # would surface as a confusing "connection refused" against
    # localhost:5432 instead of the configured target. Pass the full
    # environment explicitly so the subprocess sees what this process
    # loaded from .env.
    server_params = StdioServerParameters(command=command, args=args, env=os.environ.copy())
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _mcp_tools_to_anthropic(tools: list[Any]) -> list[dict[str, Any]]:
    """Translate MCP Tool objects (name, description, inputSchema) into
    the Anthropic Messages API tool-use format. Single source of truth
    for the contract stays in mcp_server/server.py's @mcp.tool() defs."""
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        }
        for tool in tools
    ]


def _summarize_tool_result(payload: Any, max_len: int = 200) -> str:
    text = json.dumps(payload, default=str) if not isinstance(payload, str) else payload
    return text if len(text) <= max_len else text[:max_len] + "...(truncated for display)"


async def _call_mcp_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> tuple[Any, bool]:
    result = await session.call_tool(name, arguments)
    text_parts = [block.text for block in result.content if getattr(block, "type", None) == "text"]
    raw_text = "\n".join(text_parts)
    try:
        payload = json.loads(raw_text) if raw_text else {}
    except json.JSONDecodeError:
        payload = raw_text
    return payload, bool(result.isError)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull the final JSON object out of the model's last message,
    tolerating an accidental markdown fence even though the prompt asks
    for none."""
    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else stripped
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AgentRunError(
            f"Agent's final message was not valid JSON matching the findings shape: {exc}\n"
            f"Raw message: {stripped[:2000]}"
        ) from exc


async def _run_react_loop(
    session: ClientSession,
    system_prompt: str,
    user_prompt: str,
    max_tool_calls: int,
    on_progress: ProgressCallback | None = None,
    validator: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], list[ToolCallEvent], str]:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    mcp_tools = (await session.list_tools()).tools
    tools = _mcp_tools_to_anthropic(mcp_tools)

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    tool_call_events: list[ToolCallEvent] = []
    calls_made = 0
    stopped_reason = "completed"

    while True:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
            system=system_prompt,
            messages=messages,
            tools=tools,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            parsed = _extract_json_object(final_text)
            if validator:
                validator(parsed)
            return parsed, tool_call_events, stopped_reason

        if calls_made >= max_tool_calls:
            # Force a final answer instead of silently truncating mid-loop.
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"You have reached the tool-call budget ({max_tool_calls}). "
                        "Stop investigating and respond now with the final JSON object "
                        "for everything you have already covered, listing anything you "
                        "did not get to under tables_not_audited."
                    ),
                }
            )
            stopped_reason = "max_tool_calls_reached"
            final_response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.max_tokens,
                system=system_prompt,
                messages=messages,
            )
            final_text = "".join(
                block.text for block in final_response.content if getattr(block, "type", None) == "text"
            )
            parsed = _extract_json_object(final_text)
            if validator:
                validator(parsed)
            return parsed, tool_call_events, stopped_reason

        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            calls_made += 1
            payload, is_error = await _call_mcp_tool(session, block.name, block.input)
            event = ToolCallEvent(
                tool_name=block.name,
                arguments=block.input,
                result_summary=_summarize_tool_result(payload),
                is_error=is_error,
            )
            tool_call_events.append(event)
            if on_progress:
                on_progress(event)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(payload, default=str),
                    "is_error": is_error,
                }
            )

        messages.append({"role": "user", "content": tool_results})


async def run_audit_async(
    scope_description: str,
    max_tool_calls: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> AuditRunResult:
    """Run a full data quality audit. `scope_description` is a natural-
    language instruction, e.g. "Audit all tables in schema public" or
    "Audit only tables: orders, customers in schema public"."""
    if not settings.is_configured():
        raise AgentRunError("ANTHROPIC_API_KEY is not set - see .env.example.")

    run_id = str(uuid.uuid4())

    def _validate(parsed: dict[str, Any]) -> None:
        # The agent is instructed to echo run_id back; backfill it before
        # validating so a model that drops it doesn't fail the run over
        # metadata we already know authoritatively on our side.
        parsed.setdefault("run_id", run_id)
        validate_findings(parsed)

    async with _mcp_session() as session:
        findings, tool_calls, stopped_reason = await _run_react_loop(
            session,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=f"{scope_description}\n\n(run_id for this audit: {run_id})",
            max_tool_calls=max_tool_calls or settings.max_tool_calls,
            on_progress=on_progress,
            validator=_validate,
        )
    findings.setdefault("run_id", run_id)
    return AuditRunResult(run_id=run_id, findings=findings, tool_calls=tool_calls, stopped_reason=stopped_reason)


async def inspect_schema_async(
    scope_description: str = "Inspect all schemas and tables visible to the configured role.",
    on_progress: ProgressCallback | None = None,
) -> AuditRunResult:
    """Lightweight, tool-restricted-by-prompt schema browse (FR-110/112)."""
    if not settings.is_configured():
        raise AgentRunError("ANTHROPIC_API_KEY is not set - see .env.example.")

    run_id = str(uuid.uuid4())
    async with _mcp_session() as session:
        findings, tool_calls, stopped_reason = await _run_react_loop(
            session,
            system_prompt=SCHEMA_INSPECTION_SYSTEM_PROMPT,
            user_prompt=scope_description,
            max_tool_calls=10,
            on_progress=on_progress,
        )
    return AuditRunResult(run_id=run_id, findings=findings, tool_calls=tool_calls, stopped_reason=stopped_reason)


# --- Synchronous wrappers for Streamlit -------------------------------------

def run_audit(scope_description: str, max_tool_calls: int | None = None,
              on_progress: ProgressCallback | None = None) -> AuditRunResult:
    import asyncio

    return asyncio.run(run_audit_async(scope_description, max_tool_calls, on_progress))


def inspect_schema(scope_description: str = "Inspect all schemas and tables visible to the configured role.",
                    on_progress: ProgressCallback | None = None) -> AuditRunResult:
    import asyncio

    return asyncio.run(inspect_schema_async(scope_description, on_progress))
