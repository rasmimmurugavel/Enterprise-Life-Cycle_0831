# Test Execution Summary
## Data Quality & Governance Agent - Initial Build Pass

| Field | Value |
|---|---|
| Document ID | EXEC-DQGA-09 |
| Traces from | `05-test-plan/Test-Plan.md`, `06-test-cases/`, `08-traceability/RTM.md` |
| Environment | Build/dev sandbox - no live Postgres instance, no `ANTHROPIC_API_KEY` configured |

## 1. Purpose of this document

This is a record of what was **actually executed** during the initial
build of this system, as distinct from what the code is *designed* to
do. Per this project's own principle (BR-05/BR-06 - findings must be
reproducible from evidence, not asserted), this document does not
claim a test passed unless it was actually run and its output observed.
Where the build environment couldn't run something (no live database,
no API key), that is stated plainly rather than left ambiguous.

## 2. What was executed, and what it showed

### 2.1 Read-only enforcement (NFR-201) - `mcp_server/tools/db.py::assert_select_only`

Ran the AST guard directly against 7 cases: a bare `SELECT`, a
`WITH ... SELECT`, a stacked multi-statement query, a bare `DELETE`, a
`DELETE` hidden inside a CTE, a bare `INSERT`, and a `DROP TABLE`.
**Result: all 7 matched expected accept/reject behavior.** Covers
TC-020 through TC-026.

### 2.2 Identifier-injection guard (EC-001 / DEF-001)

Constructed the adversarial column name
`x" or pg_sleep(999) --` and ran it through the query-building path
both before and after the fix. **Before**: parsed as a valid single
`SELECT` with an injected `pg_sleep(999)` boolean expression - the
statement-type AST guard alone did not catch it. **After**
(`quote_ident`): the entire payload collapsed into one literal
`Identifier` node - confirmed via `sqlglot.parse_one(...).expressions`.
See `07-edge-cases/Edge-Case-Catalog.md` EC-001 and
`10-defects/Defect-Log.md` DEF-001 for full detail. This is the single
most significant thing this execution pass found.

### 2.3 PII detection and masking - `mcp_server/tools/pii.py`

Ran `classify_columns`/`mask_row` against a synthetic row set with an
email and a phone column among non-PII columns. **Result**: both PII
columns correctly classified and masked (e.g. `j***@***.test`,
`***-***-4567`); the non-PII `notes` column passed through unchanged;
no raw value appeared in any masked output. Covers the masking
half of TC-050.

### 2.4 Audit log - `mcp_server/tools/audit_log.py`

Exercised `timed_tool_call` for both a successful call and one that
raised an exception, then read them back with `read_recent`.
**Result**: both entries logged correctly, including `status="error"`
and the exception message on the failure path; file opened only in
append mode throughout (code path never opens with `"w"`). Covers
TC-060, TC-061, TC-062.

### 2.5 Configuration loading - `mcp_server/config.py`

Imported `settings` with no `.env` present and confirmed sane defaults
(`redacted_target()`, `max_rows`, `statement_timeout_ms`,
`allowed_schemas`) load without error. Covers part of TC-005.

### 2.6 MCP server registration and transport - `mcp_server/server.py`

- Imported the module against `mcp==1.29.1` (see §3 for why this
  version) and confirmed all 9 tools (`list_schemas`, `inspect_schema`,
  `profile_table`, `top_values`, `check_referential_integrity`,
  `check_duplicates`, `detect_pii`, `run_readonly_query`,
  `get_audit_log`) register under FastMCP. Covers TC-071.
- Launched the server as a real subprocess (`python -m
  mcp_server.server`) and connected a real `mcp.ClientSession` over
  stdio: `list_tools()` returned all 9 tools; `call_tool("list_schemas",
  {})` against an unreachable Postgres correctly returned
  `CallToolResult(isError=True)` with a clear connection-refused
  message rather than crashing the server process. Covers TC-070.

### 2.7 Agent engine - `app/agent.py`

- Imported against the real `anthropic` and `mcp` SDKs; exercised the
  pure helper functions (`_extract_json_object` against plain JSON, a
  markdown-fenced JSON block, and malformed text; `_mcp_tools_to_anthropic`
  against a fake MCP `Tool` object; `_summarize_tool_result` for
  truncation).
- **Found and fixed a real bug**: `mcp.client.stdio` does not inherit
  the parent process's environment by default (only a filtered safe
  subset - `PATH`/`HOME`/etc). Without explicitly passing
  `env=os.environ.copy()` into `StdioServerParameters`, the MCP server
  subprocess would silently ignore every `PG*`/`DATABASE_URL`/`DQ_*`
  variable loaded from `.env` and always fall back to
  `config.py`'s bare defaults. Verified with a live stdio smoke test
  against a nonexistent port (`59999`): failed against the *wrong*
  port (5432, the hardcoded default) before the fix, and the
  *configured* port after it. Fixed in
  `app/agent.py::_mcp_session`. This is the kind of bug that would
  have silently broken every real deployment.
- `validate_findings` tested against a schema-conformant payload
  (passes) and one with an invalid `dimension` enum value (raises
  `AgentRunError` with a clear path/message).

### 2.8 Streamlit UI - `app/app.py`

Launched the app with `streamlit run`, confirmed HTTP 200, then used a
real headless Chromium (Playwright) to screenshot and interact with it:
initial load (sidebar renders connection/governance/model info,
correctly flags missing `ANTHROPIC_API_KEY`), clicking **Inspect
Schema** with no API key configured (fails via `AgentRunError`,
`st.status` turns red with the exact error message visible on expand,
no crash), the **Run Audit** tab (scope multiselect, tool-call budget
number input both render and accept input), and the **Audit Log** tab
(correctly read and tabulated real entries written earlier to
`audit_log/audit.jsonl` by the stdio smoke test in §2.6/2.7 - confirms
the log-reading path hits the real file, not a mock). **Found and
fixed**: `use_container_width=True` is deprecated as of the installed
Streamlit (1.63) and logged a warning on every chart render; switched
to `width='stretch'` and bumped the `requirements.txt` floor
accordingly. Covers TC-080, TC-082, TC-083, TC-084, TC-088.

### 2.9 Eval scoring logic - `eval/eval_runner.py`

Ran `score_fixture_result`/`aggregate` against two synthetic agent
outputs for the `nulls_and_dupes` fixture: a "good" run (all 3 golden
findings matched, correct-ish severities, one tolerated extra finding,
no PII leak - **recall 100%, precision 75%, gate: PASS**) and a
deliberately "bad" run (missed 2 of 3 findings, under-called severity
on the third, and a raw PII value injected into the fake transcript -
**recall 33%, severity accuracy 0%, 1 PII leak incident, gate: FAIL**,
correctly citing all four failure reasons). Confirms the scoring math
and release gate behave as designed without needing a live model or
database.

### 2.10 Dependency/version issue found

`mcp` released a breaking v2.0 (renamed `FastMCP` to `MCPServer`,
changed server internals) very recently. Discovered when a fresh
`pip install` pulled 2.1.1 and `mcp_server/server.py` failed to
import. Pinned `mcp>=1.2.0,<2.0.0` in `requirements.txt` and
re-verified §2.6/2.7 against the pinned version.

## 3. What was NOT executed (blocked on environment, not skipped)

| Not executed | Blocked on | Tracked as |
|---|---|---|
| Any test requiring a live Postgres connection (schema inspection, profiling, referential integrity, duplicate checks, row caps, statement timeout against a real query) - TC-010 through TC-030, TC-040-048 as full end-to-end runs | No Postgres instance available in the build sandbox | `08-traceability/RTM.md` "blocked" rows; `docker-compose.yml` (added next) removes this blocker for local dev |
| Any test requiring a real Anthropic API call (a full agent audit run producing real findings, TC-045-048, TC-081, TC-085-087) | No `ANTHROPIC_API_KEY` configured/available in the build sandbox | Same |
| `eval/eval_runner.py`'s actual end-to-end run against the four fixtures | Requires both of the above | `12-eval-rubrics/Eval-Rubric-Spec.md` §6 gives the exact commands to run it once credentials are available |
| UAT (`11-uat-and-signoff/`) | Requires a completed real audit run for a human reviewer to assess | Not started this pass |
| FR-132 (governance override persistence) | Not implemented this pass | DEF-002, `10-defects/Defect-Log.md` |

## 4. Recommendation before first production release

Run `eval/eval_runner.py` against all four fixtures with real
credentials (per `12-eval-rubrics/Eval-Rubric-Spec.md` §6) and confirm
`PASS` against the release gate, then complete UAT
(`11-uat-and-signoff/`), before treating this system as
production-ready. Everything in §2 gives high confidence in the
governance/plumbing layer; nothing in this pass yet demonstrates the
agent's actual judgment against a real model.
