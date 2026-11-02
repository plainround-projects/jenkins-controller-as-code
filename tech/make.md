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







<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of the `Makefile`

`make` is a program that reads a file called `Makefile`. The file is a list of **rules**. A rule has a **target** (a name, written before a colon), optional **prerequisites** (written after the colon: things that must exist or be built first), and a **recipe** (the indented lines underneath: shell commands to run). You type `make up` and make finds the rule whose target is `up`, builds its prerequisites first, then runs its recipe. Recipe lines must start with a Tab character, not spaces; that is a rule of the `make` language. Each recipe line is run in its own fresh shell, so a `cd` on one line does not carry over to the next line.

```make
# make up | run | test | lint | down      (make help lists everything)
PYTHON ?= $(shell command -v python3.13 || command -v python3.12 || command -v python3)
VENV := .venv
PY := $(VENV)/bin/python
STAMP := $(VENV)/.installed
SCRIPTS := $(wildcard scripts/*.sh pipeline/scripts/*.sh agent/entrypoint.sh services/git-server/entrypoint.sh)
```
- Line 1 is a comment (a line starting with `#` is ignored by make). It is the one-line summary of what you can type.
- Line 2 defines a variable called `PYTHON`. `?=` means "set it only if it was not already set", so you can override it by running `make PYTHON=python3.12 install`. `$(shell ...)` runs a shell command and uses its output as the value. `command -v python3.13` prints the path of `python3.13` if it exists. `||` means "if the left side failed, try the right side", so the chain picks the first of Python 3.13, 3.12 or plain `python3` that exists on your computer.
- Line 3 defines `VENV` as `.venv`. `:=` means "evaluate right now, once", unlike `=`, which re-evaluates each time the variable is used. A **virtual environment** (venv) is a private folder holding one project's Python packages so they do not mix with the rest of your computer.
- Line 4 builds `PY`, the path to the Python program inside that folder. `$(VENV)` is how make writes "the value of the variable VENV".
- Line 5 defines `STAMP` as a file inside the venv. It is never meant to hold data; it is a marker file whose modification time says "the packages were installed at this moment".
- Line 6 defines `SCRIPTS`, the list of every shell script in the repository. `$(wildcard ...)` expands patterns such as `scripts/*.sh` into the matching file names, the same way a shell would. ShellCheck (see `shellcheck.md`) is later given this list.

```make
.PHONY: help install up run test test-offline test-stack rebuild-proof lint lint-app lint-jenkinsfile format audit plugins-lock seed logs down clean
```
`.PHONY` lists targets that are *names of actions*, not names of files. Without it, make would look for a file called `up`, and if one existed it would say "nothing to do". Marking a target phony forces its recipe to run every time.

```make
help: ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort
```
- Line 10 is the `help` target. The text after `##` is not a comment for make; it is a convention this file uses as a one-line description that the `help` recipe can find.
- Line 11 starts with `@`, which tells make not to print the command before running it. `grep -E` searches with an extended regular expression: lines that begin with lowercase letters and dashes, then a colon, then anything, then `## `. `$(MAKEFILE_LIST)` is the list of makefiles read (here just this one). The result goes through a pipe (`|`, which sends one program's output into the next program's input) to `sed -E 's/:.*## /\t/'`, which replaces everything between the first colon and the `## ` with a Tab. Finally `sort` puts the lines in alphabetical order. The output is a two-column list of target and description.

```make
$(STAMP): requirements-dev.lock pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -q --require-hashes -r requirements-dev.lock
	touch $@

install: $(STAMP) ## create .venv from the lock file
```
- Line 13 is a **file rule**: the target is the marker file `$(STAMP)` and its prerequisites are `requirements-dev.lock` and `pyproject.toml`. Make compares modification times. If either prerequisite is newer than the stamp (or the stamp is missing), make re-runs the recipe; otherwise it skips it. This is how "install only when the dependency list changed" works without any extra code.
- Line 14 creates the virtual environment with `python -m venv`.
- Line 15 installs packages into it with `pip`. `-q` is quiet. `--require-hashes` makes pip refuse any package whose file does not match a SHA-256 fingerprint written in the lock file, so a tampered download is rejected. `-r` names the file to read the package list from.
- Line 16 `touch $@` creates or updates the stamp file. `$@` is a make automatic variable that means "the target of this rule".
- Line 18 is the friendly name `install`. It has no recipe of its own; it only depends on the stamp, so `make install` means "make sure the stamp is up to date".

```make
up: $(STAMP) ## create .env, build the images, start the controller, agent and services, seed the job's repository
	./scripts/up.sh

seed: ## push the current files to the Git server the job builds from
	./scripts/seed-project.sh

run: $(STAMP) ## the scripted end-to-end run: trigger the job through the API and assert every result (needs make up)
	$(PY) -m pytest tests/stack -m "stack and not rebuild" -v -s

rebuild-proof: $(STAMP) ## destroy the controller and its volume, start it again, compare the configuration (slow)
	$(PY) -m pytest tests/stack -m rebuild -v -s
```
- `up` needs the venv (the `$(STAMP)` prerequisite) and then runs `./scripts/up.sh`, which creates the credential file, builds the images and starts the containers (explained in `bash.md`).
- `seed` pushes the repository files to the Git server container that the Jenkins job later builds from.
- `run` is the end-to-end test: `python -m pytest` with `tests/stack` as the folder to search, `-m "stack and not rebuild"` to select only tests carrying the `stack` marker and not the `rebuild` marker, `-v` for verbose test names and `-s` to show the program's own printed output instead of capturing it.
- `rebuild-proof` runs only the test marked `rebuild`, the slow one that destroys and recreates the controller.

```make
lint: $(STAMP) lint-app ## yamllint, shellcheck, ruff, mypy, compose config and the Java project's checkstyle
	$(VENV)/bin/yamllint -s .
	shellcheck $(SCRIPTS)
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/mypy
	ADMIN_PASSWORD=x PUBLISH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx docker compose config --quiet
```
`lint` runs every static check, none of which start a container:

- `yamllint -s .` checks YAML style in every folder; `-s` means "strict": warnings count as failures.
- `shellcheck $(SCRIPTS)` analyses the shell scripts for bugs.
- `ruff check .` looks for Python mistakes and `ruff format --check .` verifies the formatting without changing files.
- `mypy` checks the Python type annotations (its settings are in `pyproject.toml`, so it needs no arguments).
- Line 38 sets two environment variables only for this one command (`NAME=value command` is shell syntax for that) and runs `docker compose config --quiet`. `config` makes Compose parse and validate `docker-compose.yml` and expand its variables; `--quiet` prints nothing when it is valid. The two dummy values satisfy the `:?` "must be set" rules in the compose file, which would otherwise fail without a `.env` file.

```make
lint-app: ## checkstyle over the Java project
	cd app && ./mvnw --batch-mode --no-transfer-progress checkstyle:check

lint-jenkinsfile: ## ask the running controller's declarative linter about the Jenkinsfile (needs make up)
	./scripts/lint-jenkinsfile.sh

format: $(STAMP) ## format the Python
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .
```
- `lint-app` changes into the `app` folder (`cd app &&` runs the next command only if the `cd` worked) and runs the Maven wrapper with `checkstyle:check`. `--batch-mode` turns off interactive colours and prompts, `--no-transfer-progress` hides the download progress bars.
- `lint-jenkinsfile` runs a script that sends the `Jenkinsfile` to the running controller's own syntax checker.
- `format` rewrites the Python in place: `ruff format .` reformats, `ruff check --fix .` applies safe automatic fixes.

```make
test-offline: $(STAMP) ## unit tests of the scripts, the artifact store, the configuration and the Jenkinsfile; no containers
	$(PY) -m pytest -m "not stack" --cov --cov-report=term-missing

test-stack: run ## alias of run

test: $(STAMP) ## offline tests, the Java project's tests, then the end-to-end run (needs make up)
	$(PY) -m pytest -m "not stack" --cov --cov-report=term-missing
	cd app && ./mvnw --batch-mode --no-transfer-progress verify
	$(PY) -m pytest tests/stack -m "stack and not rebuild"
```
- `test-offline` runs pytest on everything that is *not* marked `stack`, so it needs no containers. `--cov` turns on coverage measurement and `--cov-report=term-missing` prints, per file, the line numbers that no test executed.
- `test-stack` is an alias: its only prerequisite is `run`, and it has no recipe.
- `test` chains three steps: the offline tests, then `mvnw ... verify` (compile, unit tests, integration tests and coverage check for the Java project), then the stack tests. If any recipe line exits with an error, make stops there.

```make
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
```
- `audit` installs `pip-audit` at one exact version and checks each locked package against a database of known vulnerabilities. The `--require-hashes` flag makes it read the lock exactly as pip would.
- `plugins-lock` runs the script that turns the short plugin list into the exact one (`python.md` walks through that script).
- `logs` follows (`--follow`) the controller container's log output.
- `down` calls the script that stops the containers and deletes their volumes.
- `clean` deletes the venv and tool caches. `rm -rf` removes files and folders without asking and without complaining if they are absent.

Nothing in this Makefile is skipped above: lines 7, 9, 12, 17, 19, 25, 31, 39, 45, 49, 57 and 59 are blank separators.
<!-- full-walkthrough:end -->

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
