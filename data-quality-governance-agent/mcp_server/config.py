"""Configuration for the Data Quality & Governance MCP server.

Everything here is read from the environment (see ../.env.example). No
connection parameters or governance limits are ever hard-coded, per
FR-101 and BR-07 in 02-requirements/FRD-SRS.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- Postgres connection ---
    database_url: str | None = os.getenv("DATABASE_URL")
    pg_host: str = os.getenv("PGHOST", "localhost")
    pg_port: int = int(os.getenv("PGPORT", "5432"))
    pg_database: str = os.getenv("PGDATABASE", "postgres")
    pg_user: str = os.getenv("PGUSER", "postgres")
    pg_password: str = os.getenv("PGPASSWORD", "")
    pg_sslmode: str = os.getenv("PGSSLMODE", "prefer")

    # --- Governance limits (BR-07, NFR-201/202) ---
    allowed_schemas: tuple[str, ...] = field(
        default_factory=lambda: tuple(_split_csv(os.getenv("DQ_ALLOWED_SCHEMAS", "")))
    )
    max_rows: int = int(os.getenv("DQ_MAX_ROWS", "500"))
    statement_timeout_ms: int = int(os.getenv("DQ_STATEMENT_TIMEOUT_MS", "10000"))
    max_tool_calls: int = int(os.getenv("DQ_MAX_TOOL_CALLS", "40"))

    # --- PII detection (FR-130/131) ---
    pii_flag_threshold: float = float(os.getenv("DQ_PII_THRESHOLD", "0.05"))
    pii_sample_rows: int = int(os.getenv("DQ_PII_SAMPLE_ROWS", "200"))

    # --- Audit log (FR-140/141, NFR-205) ---
    audit_log_path: str = os.getenv("DQ_AUDIT_LOG_PATH", "./audit_log/audit.jsonl")

    def dsn(self) -> str:
        """Build a libpq connection string. Never logged (NFR-205)."""
        if self.database_url:
            return self.database_url
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_database} "
            f"user={self.pg_user} password={self.pg_password} sslmode={self.pg_sslmode}"
        )

    def redacted_target(self) -> str:
        """A safe-to-display description of the connection target (no credentials)."""
        if self.database_url:
            # Strip credentials from a DSN-style URL for display purposes only.
            if "@" in self.database_url:
                scheme_and_creds, rest = self.database_url.split("@", 1)
                scheme = scheme_and_creds.split("://", 1)[0]
                return f"{scheme}://***@{rest}"
            return self.database_url
        return f"{self.pg_user}@{self.pg_host}:{self.pg_port}/{self.pg_database}"

    def is_schema_allowed(self, schema: str) -> bool:
        if not self.allowed_schemas:
            return True
        return schema in self.allowed_schemas


settings = Settings()
