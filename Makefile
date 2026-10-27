# make up | run | test | lint | down      (make help lists everything)
PYTHON ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
VENV := .venv
PY := $(VENV)/bin/python
STAMP := $(VENV)/.installed
SCRIPTS := $(wildcard scripts/*.sh pipeline/scripts/*.sh agent/entrypoint.sh services/git-server/entrypoint.sh)

.PHONY: help install up run test test-offline test-stack rebuild-proof lint lint-app lint-jenkinsfile format audit plugins-lock seed logs down clean

help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort

$(STAMP): requirements-dev.lock pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --require-hashes -r requirements-dev.lock
	touch $@

install: $(STAMP) ## create .venv from the lock file

up: $(STAMP) ## create .env, build the images, start the controller, agent and services, seed the job's repository
	./scripts/up.sh

seed: ## push the current files to the Git server the job builds from
	./scripts/seed-project.sh

run: $(STAMP) ## the scripted end-to-end run: trigger the job through the API and assert every result (needs make up)
	$(PY) -m pytest tests/stack -m "stack and not rebuild" -v -s

rebuild-proof: $(STAMP) ## destroy the controller and its volume, start it again, compare the configuration (slow)
	$(PY) -m pytest tests/stack -m rebuild -v -s

lint: $(STAMP) lint-app ## yamllint, shellcheck, ruff, mypy, compose config and the Java project's checkstyle
	$(VENV)/bin/yamllint -s .
	shellcheck $(SCRIPTS)
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/mypy
	ADMIN_PASSWORD=x PUBLISH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx docker compose config --quiet

lint-app: ## checkstyle over the Java project
	cd app && ./mvnw --batch-mode --no-transfer-progress checkstyle:check

lint-jenkinsfile: ## ask the running controller's declarative linter about the Jenkinsfile (needs make up)
	./scripts/lint-jenkinsfile.sh

format: $(STAMP) ## format the Python
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

test-offline: $(STAMP) ## unit tests of the scripts, the artifact store, the configuration and the Jenkinsfile; no containers
	$(PY) -m pytest -m "not stack" --cov --cov-report=term-missing

test-stack: run ## alias of run

test: $(STAMP) ## offline tests, the Java project's tests, then the end-to-end run (needs make up)
	$(PY) -m pytest -m "not stack" --cov --cov-report=term-missing
	cd app && ./mvnw --batch-mode --no-transfer-progress verify
	$(PY) -m pytest tests/stack -m "stack and not rebuild"

audit: $(STAMP) ## known-vulnerability check of the locked Python dependencies
	$(VENV)/bin/pip install -q pip-audit==2.9.0
	$(VENV)/bin/pip-audit --require-hashes -r requirements-dev.lock

plugins-lock: ## resolve controller/plugins.txt into controller/plugins.lock.txt
	python3 scripts/plugins_lock.py

logs: ## follow the controller's log
	docker compose logs --follow controller

down: ## stop everything and delete the volumes
	./scripts/down.sh

clean: ## remove the virtual environment, caches and build output
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov app/target
