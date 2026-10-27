# GNU Make

## 1. What it is

Make is a command-line tool that runs named recipes from a file called `Makefile`. Each recipe is a **target**. A target can list other targets or files it **depends on**, and Make runs those first. People use it as a short front door to a project: `make test` instead of remembering a long command.

## 2. Why this repository uses it

`make up`, `make run`, `make test`, `make lint`, `make rebuild-proof` and `make down` are the interface. The Makefile also builds the Python test environment from a lock file.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `Makefile` | targets, the virtual-environment stamp, the `help` listing |

## 4. How it works underneath

- A rule looks like `target: dependency` followed by lines that start with a **tab** character. Those lines are the recipe; Make hands each line to the shell.
- When a target is a *file name*, Make compares file times: if a dependency is newer than the target, the recipe runs again; if not, Make skips it. This is how a virtual environment is built only when its lock file changes.
- A target that is not a file (`up`, `test`) is declared `.PHONY` so Make never mistakes it for a file called `up`.
- `$(NAME)` reads a variable. `?=` sets it only if the caller did not. `:=` evaluates immediately. `$$` writes a single `$` for the shell. `$@` is the target's own name.
- A line starting with `@` is not echoed. A recipe line that fails stops the whole target.
- `## text` after a target is just a comment this repository's `help` target reads back with `grep`.

## 5. Walkthrough of this repository's use

```make
PYTHON ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
VENV := .venv
PY := $(VENV)/bin/python
STAMP := $(VENV)/.installed
.PHONY: help install up run test ... down clean
help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /	/' | sort
$(STAMP): requirements-dev.lock pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --require-hashes -r requirements-dev.lock
	touch $@
```
`?=` takes the caller's `PYTHON` if given, otherwise the newest Python found; `:=` fixes the other values now. `.PHONY` names the targets that are commands, not files. `help` greps the file for lines with `## ` and prints them sorted (`@` hides the command line). `$(STAMP)` is a **file target**: when the lock file or `pyproject.toml` is newer than `.venv/.installed`, Make rebuilds the environment (`touch $@` renews the stamp; `$@` is the target's name). Targets that need the tools list `$(STAMP)` as a dependency.

Differences specific to this repository:

```make
SCRIPTS := $(wildcard scripts/*.sh pipeline/scripts/*.sh agent/entrypoint.sh services/git-server/entrypoint.sh)
run: $(STAMP) ## the scripted end-to-end run: trigger the job through the API and assert every result (needs make up)
	$(PY) -m pytest tests/stack -m "stack and not rebuild" -v -s
rebuild-proof: $(STAMP)
	$(PY) -m pytest tests/stack -m rebuild -v -s
```
`run` is a pytest run of the stack tests (`-m "stack and not rebuild"` selects tests with the `stack` marker, minus the slow `rebuild` one; `-v` verbose, `-s` shows output as it happens). `rebuild-proof` runs only the rebuild test.

```make
lint: $(STAMP) lint-app
	$(VENV)/bin/yamllint -s .
	shellcheck $(SCRIPTS)
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/mypy
	ADMIN_PASSWORD=x PUBLISH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx docker compose config --quiet
lint-app:
	cd app && ./mvnw --batch-mode --no-transfer-progress checkstyle:check
```
`lint` also depends on `lint-app`, so Java style is checked first. The last line validates the Compose file: `docker compose config --quiet` parses it and prints nothing if valid. Because `docker-compose.yml` requires `ADMIN_PASSWORD` and `PUBLISH_TOKEN` (`:?`), the line gives them dummy values for this one command (a variable assignment before a command applies only to that command). `cd app && ...` works because each recipe line is one shell.

```make
test: $(STAMP)
	$(PY) -m pytest -m "not stack" --cov --cov-report=term-missing
	cd app && ./mvnw --batch-mode --no-transfer-progress verify
	$(PY) -m pytest tests/stack -m "stack and not rebuild"
```
Three steps: offline Python tests with coverage, the whole Maven lifecycle, then the end-to-end run. `plugins-lock` runs `python3 scripts/plugins_lock.py`. `logs` follows the controller's log. `down` runs `scripts/down.sh`.

## 6. Try it yourself

1. `make help` : sorted targets with descriptions.
2. `make -n test` : the three steps, not run.
3. `make lint-app` : checkstyle over the Java.
4. `make plugins-lock` : regenerates `controller/plugins.lock.txt` (needs network).
5. `make -n down`.

## 7. Mistakes people make

- **Spaces instead of a tab** in a recipe: Make says `missing separator`. The `.editorconfig` forces tabs in the Makefile.
- **Forgetting `.PHONY`**, so a file named like the target silently disables it.
- **Each recipe line runs in its own shell**, so `cd dir` on one line does not affect the next. Join lines with `&&` or `;`.
- **Putting logic in the Makefile.** Here the logic lives in scripts, which can be run, tested and shell-checked without Make.

## 8. Check yourself

1. Why must a recipe line start with a tab?
   *Answer:* That is how Make tells a recipe from a rule; spaces give a `missing separator` error.
2. What does `.PHONY` do?
   *Answer:* It marks targets that are commands, not files, so Make always runs them.
3. When does Make skip a file target?
   *Answer:* When the file exists and no dependency is newer than it.
4. What does `$$status` in a recipe become?
   *Answer:* `$status` in the shell, because Make turns `$$` into one `$`.
5. Why does a failing line stop the target?
   *Answer:* Make treats a non-zero exit from a recipe line as an error, unless the line starts with `-`.

## 9. Further reading

- GNU Make manual: <https://www.gnu.org/software/make/manual/make.html>. The Mac that built this uses GNU Make 3.81 from the system; CI uses GNU Make 4.3. The Makefile uses only features both have.
