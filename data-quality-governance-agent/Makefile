.PHONY: install run mcp-server test test-live docker-up docker-down seed eval clean

install:
	pip install -r requirements.txt

# Streamlit UI - the full app (spawns the MCP server itself as a subprocess).
run:
	streamlit run app/app.py

# The MCP server standalone (FR-150) - e.g. for pointing Claude Desktop/
# Claude Code at the same tools outside this app.
mcp-server:
	python -m mcp_server.server

# Fast unit tests only - no database needed, safe to run on every save.
test:
	python3 -m pytest tests/ -v

# Same suite, but with the live-integration tests included (auto-skipped
# in `make test` when no DB is configured) - requires `make docker-up` first.
test-live: docker-up
	python3 -m pytest tests/ -v

docker-up:
	docker compose up -d
	@echo "Waiting for Postgres to be healthy..."
	@until docker compose ps postgres | grep -q "healthy"; do sleep 1; done
	@echo "Postgres ready at localhost:5432 (db=dq_dev, seeded from db/seed/)."

docker-down:
	docker compose down

# Re-run the seed scripts against an already-running database (e.g. after
# editing a fixture) without recreating the container.
seed:
	@test -n "$$DQ_EVAL_ADMIN_DATABASE_URL$$DATABASE_URL" || \
		(echo "Set DQ_EVAL_ADMIN_DATABASE_URL or DATABASE_URL first (see db/README.md)."; exit 1)
	for f in db/seed/*.sql; do \
		psql "$${DQ_EVAL_ADMIN_DATABASE_URL:-$$DATABASE_URL}" -v ON_ERROR_STOP=1 -f "$$f"; \
	done

# Runs the real agent against every eval fixture and scores it against
# the release gate (eval/rubrics.yaml) - needs ANTHROPIC_API_KEY and a
# seeded database (see 12-eval-rubrics/Eval-Rubric-Spec.md).
eval:
	python -m eval.eval_runner

clean:
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache audit_log
