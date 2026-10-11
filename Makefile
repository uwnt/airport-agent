# Short names for the commands we run most. Targets for run, refresh and docker arrive with their steps.
.PHONY: test lint format ci

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

format:
	uv run ruff format . && uv run ruff check --fix .

ci:
	scripts/ci-local
