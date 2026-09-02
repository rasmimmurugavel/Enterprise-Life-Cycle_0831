"""Agent-host-process configuration.

Separate from mcp_server/config.py deliberately: the MCP server
subprocess only ever needs DB + governance settings, while the agent
host process additionally needs the Anthropic credentials. Splitting
them means the MCP server's env never needs to carry an LLM API key at
all if it's ever run standalone (e.g. attached to Claude Desktop
instead of this app).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AgentSettings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    max_tool_calls: int = int(os.getenv("DQ_MAX_TOOL_CALLS", "40"))
    max_tokens: int = int(os.getenv("DQ_AGENT_MAX_TOKENS", "8192"))
    rubrics_path: str = os.getenv("DQ_RUBRICS_PATH", "eval/rubrics.yaml")
    findings_schema_path: str = os.getenv(
        "DQ_FINDINGS_SCHEMA_PATH", "eval/schemas/findings.schema.json"
    )
    # Launch command for the MCP server subprocess (FR-150: standalone,
    # reusable outside Streamlit - this is the same command Claude
    # Desktop/Code would use in an mcp.json entry).
    mcp_server_command: tuple[str, ...] = field(
        default_factory=lambda: (sys.executable, "-m", "mcp_server.server")
    )

    def is_configured(self) -> bool:
        return bool(self.anthropic_api_key)


settings = AgentSettings()
