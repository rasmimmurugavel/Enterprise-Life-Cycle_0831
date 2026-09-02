# Data Quality & Governance Agent

An autonomous AI agent that audits PostgreSQL databases for data
quality defects and governance risk - built with **Streamlit**, the
**Anthropic Claude API**, and the **Model Context Protocol (MCP)** -
designed from the ground up to be audit-ready: read-only by
construction, PII-masked before anything reaches the model, every
action logged, and its judgment scored against versioned rubrics
before a release ships.

```
Streamlit UI  →  Claude agent engine (ReAct loop)  →  MCP server  →  PostgreSQL
  (app/app.py)      (app/agent.py)                   (mcp_server/)   (read-only role)
```

See `03-design/HLD.md` for the full architecture and
`AUDIT-READINESS.md` for a one-page map from compliance control to
implementation.

## Quickstart (local dev)

```bash
cp .env.example .env               # then fill in ANTHROPIC_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d               # Postgres 16, auto-seeded with eval fixtures
# .env's PGUSER/PGPASSWORD/PGDATABASE defaults already match what
# docker-compose seeds (dq_audit_reader / devpassword / dq_dev) - see
# db/README.md if you're pointing at a different database.

make test                          # unit tests + live integration tests (fast)
make run                           # streamlit run app/app.py
```

No Docker? Any local Postgres 16+ works - see `db/README.md`.

## What it does

1. **Inspect Schema** - lists every table, column, type, PK/FK visible
   to the configured role. No data is read.
2. **Run Audit** - the agent runs a data-quality baseline (null rates,
   duplicate keys, orphaned foreign keys, PII detection) on every
   table in scope, then decides what else to investigate based on
   what it finds - all through a fixed, governed set of MCP tools, all
   read-only, all logged.
3. **Scorecard + report** - a 0-100 score per quality dimension
   (completeness, validity, uniqueness, consistency, timeliness) per
   table and per database, a severity-ranked findings list, and a
   downloadable, self-contained Markdown report.
4. **Audit Log** - every tool call the agent ever made, independent of
   what made it into a report - the source of truth for "what did this
   thing actually do."

## Why MCP, not just direct tool-use

The Postgres tools (`mcp_server/`) are a standalone MCP server, not
code wired only into the Streamlit app. Run it on its own:

```bash
python -m mcp_server.server
```

and any MCP-compatible client - Claude Code, Claude Desktop, or this
app's own `app/agent.py` - can attach to the exact same governed tool
surface. The tool contract lives in exactly one place.

## Project layout

| Path | What |
|---|---|
| `mcp_server/` | The governed, read-only Postgres tool server (schema inspection, profiling, referential integrity, PII detection, audit logging) |
| `app/` | The Streamlit UI + the Claude agent engine (ReAct loop, MCP client) |
| `eval/` | Automated eval rubric framework - fixtures with known-correct answers, a scoring/release-gate runner |
| `db/` | Read-only role provisioning SQL + fixture seed scripts + `docker-compose.yml`'s init data |
| `tests/` | Unit tests (no DB needed) + live integration tests (auto-skip without one) |
| `01`-`11` numbered folders | Full SDLC documentation - BRD → requirements → design → test strategy/plan/cases/edge cases → traceability → execution → defects → UAT, in the same discipline as this repo's `loan-evaluator/` example |
| `12-eval-rubrics/` | The eval framework's own spec document |
| `AUDIT-READINESS.md` | One-page compliance-control-to-implementation map |

## Governance at a glance

- **Read-only, enforced twice**: a least-privilege `SELECT`-only
  Postgres role (`db/README.md`), *and* an independent AST-level guard
  (`mcp_server/tools/db.py`) that rejects anything that isn't a single
  `SELECT`/`WITH` statement - so a misconfigured role still can't write.
- **PII never reaches the model**: masked in the governance middleware
  before a tool result is even serialized, not as a prompt instruction.
- **Every action logged**: an append-only JSONL audit trail, independent
  of the agent's own summarized findings.
- **Judgment is versioned and gated**: `eval/rubrics.yaml` defines what
  "quality" means; `eval/eval_runner.py` scores every release against
  fixed scenarios with known-correct answers before it ships.

Full detail: `AUDIT-READINESS.md`.

## Status

This is a from-scratch build, documented as it went - including three
real defects found and fixed by actually running the system rather
than just reading the code (one critical SQL-injection path, and two
that only surfaced under a real least-privilege database role). See
`09-test-execution/Execution-Summary.md` for exactly what has been
verified so far and `10-defects/Defect-Log.md` for what was found.
What's not yet done: a live-model eval run and UAT sign-off, both of
which need real credentials - see `11-uat-and-signoff/UAT.md`.

## Documentation map

Start at `01-business-requirements/BRD.md` and follow the numbered
folders in order - each stage consumes the one before it, same
traceability discipline as `loan-evaluator/` (`BR-xx` → `FR-1xx`/`NFR-2xx`
→ `TC-xxx`/`EC-xxx` → `08-traceability/RTM.md`).
