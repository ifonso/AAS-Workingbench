.DEFAULT_GOAL := help
.PHONY: help install run format format-check lint lint-fix typecheck test 	test-small test-medium test-large coverage check build

help:
	@echo "install       Install the locked environment"
	@echo "run           Start the application"
	@echo "format        Format the code"
	@echo "format-check  Fail if the code is not formatted"
	@echo "lint          Run the linter"
	@echo "lint-fix      Run the linter and apply safe fixes"
	@echo "typecheck     Run the type checker"
	@echo "test          Run small and medium tests"
	@echo "test-small    Run small tests"
	@echo "test-medium   Run medium tests"
	@echo "test-large    Run large tests (full application)"
	@echo "coverage      Run small and medium tests with coverage"
	@echo "check         Run everything CI runs"
	@echo "build         Build the stand-alone executable"

install:
	uv sync --locked

run:
	uv run python -m aas_editor

format:
	uv run ruff format

format-check:
	uv run ruff format --check

lint:
	uv run ruff check

lint-fix:
	uv run ruff check --fix

typecheck:
	uv run pyright

test:
	uv run pytest -m "small or medium"

test-small:
	uv run pytest -m small

test-medium:
	uv run pytest -m medium

test-large:
	uv run pytest -m large

coverage:
	uv run pytest -m "small or medium" --cov --cov-report=term-missing

check: format-check lint typecheck test

build:
	uv run --group build pyinstaller --noconfirm aas_manager.spec
