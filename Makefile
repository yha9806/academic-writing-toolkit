# Makefile for academic-writing-toolkit
# Run `make` (or `make help`) to see available targets.

.DEFAULT_GOAL := help
.PHONY: help setup init sync doctor repair

EDITOR ?= vi

help:  ## Show this help (default)
	@printf "academic-writing-toolkit — available make targets:\n\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nTypical first-time flow: \033[36mmake setup\033[0m\n"
	@printf "When CLAUDE.md changes:  \033[36mmake sync\033[0m\n"
	@printf "Health check anytime:    \033[36mmake doctor\033[0m\n"

setup:  ## One-time setup after clone (sets git config, syncs configs, runs doctor)
	@git config core.fileMode false
	@bash scripts/sync-config.sh
	@bash scripts/doctor.sh

init:  ## Open CLAUDE.md in $$EDITOR for first-time customisation, then sync
	@if [ ! -t 0 ]; then \
		printf "error: make init requires a tty (cannot run in CI)\n" >&2; \
		exit 1; \
	fi
	@$(EDITOR) CLAUDE.md
	@bash scripts/sync-config.sh

sync:  ## Regenerate AGENTS.md and GEMINI.md from CLAUDE.md
	@bash scripts/sync-config.sh

doctor:  ## Run all read-only health checks (CI-suitable, exit 0/1)
	@bash scripts/doctor.sh

repair:  ## Apply idempotent fixes for issues doctor flags
	@bash scripts/repair.sh
