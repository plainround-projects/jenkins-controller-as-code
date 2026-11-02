# GitHub Actions

## 1. What it is

GitHub Actions runs a **workflow** (a YAML file under `.github/workflows/`) on GitHub's machines whenever something happens, such as a push. A workflow has **jobs**; a job runs **steps** on a **runner** (a fresh virtual machine).

## 2. Why this repository uses it

The same checks run on every push, including the Java build on a clean machine, and a job that starts the whole Compose stack and runs the end-to-end test.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `.github/workflows/ci.yml` | jobs `lint`, `offline`, `stack` |

## 4. How it works underneath

- `on: [push, pull_request]` is the trigger. Each job starts on a clean machine, so each one checks out the code and installs its tools.
- `uses: actions/checkout@v4` runs a published action (a reusable step). `run:` runs a shell command. `with:` passes inputs.
- A step that exits non-zero fails its job and the check on the commit turns red.
- `echo "NAME=value" >> "${GITHUB_ENV}"` sets an environment variable for the later steps.
- Nothing runs here until the repository is pushed to GitHub; locally the same checks are `make lint` and `make test-offline`.

## 5. Walkthrough of this repository's use

```yaml
jobs:
  lint:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: "21" }
      - run: make lint
  offline:
    steps:
      ...
      - run: make test-offline
      - run: cd app && ./mvnw --batch-mode --no-transfer-progress verify
      - run: make audit
  stack:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: make up
      - run: make run
      - if: failure()
        run: docker compose logs --no-color --tail=200
```
`actions/setup-java@v4` installs a JDK (here Temurin 21) so Maven can compile. The `lint` job runs `make lint`, which includes `checkstyle:check` on the Java. The `offline` job runs the Python tests, then the whole Maven lifecycle (`verify`: compile, unit tests, package, integration tests, coverage rule), then the dependency audit. The `stack` job uses the Docker that GitHub's runners already have: `make up` builds and starts the stack, `make run` runs the end-to-end test. `if: failure()` makes the last step run **only** when an earlier step failed, printing the last 200 lines of every container's log (`--no-color` keeps the log readable). None of this has run on GitHub: the repository has not been pushed.


<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: `.github/workflows/ci.yml`

GitHub Actions runs automation on GitHub's servers when something happens in the repository. A **workflow** is a YAML file in `.github/workflows/`. It contains **jobs**; each job runs on a fresh virtual machine (the **runner**) and consists of **steps**, either `uses:` (run a ready-made action) or `run:` (run a shell command). Jobs without `needs:` run in parallel.

```yaml
---
name: ci

on: [push, pull_request]
```
`name` is the label shown on GitHub. `on: [push, pull_request]` starts the workflow whenever someone pushes a commit or opens or updates a pull request.

```yaml
jobs:
  lint:
    name: yamllint, shellcheck, ruff, mypy, compose config, checkstyle
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "21"
      - run: make lint
```
`jobs:` begins the list. The job `lint` has a `name` and runs on `ubuntu-latest`. Its steps: `actions/checkout@v4` downloads the repository into the runner; `actions/setup-python@v5` installs Python 3.12 (the `with:` block passes the action's inputs); `actions/setup-java@v4` installs Java 21 from the Temurin distribution (needed by `make lint-app`); `run: make lint` runs the whole lint target.

```yaml
  offline:
    name: Unit tests with coverage, the Java project's tests, dependency audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "21"
      - run: make test-offline
      - run: cd app && ./mvnw --batch-mode --no-transfer-progress verify
      - run: make audit
```
The `offline` job repeats the set-up and then runs three steps: the offline Python tests with coverage, the Java project's tests (`verify` runs unit tests, integration tests and the coverage check), and the dependency audit.

```yaml
  stack:
    name: Controller, agent and services in Docker Compose, and the end-to-end run
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: make up
      - run: make run
      - if: failure()
        run: docker compose logs --no-color --tail=200
```
The `stack` job sets up Python and runs `make up` (builds and starts the whole Docker Compose stack on the runner) and `make run` (the end-to-end tests). The last step has `if: failure()`, so it runs only when an earlier step failed, and prints the last 200 lines of every container's log, which is what you need to find out why.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `grep -n 'run:' .github/workflows/ci.yml` : the commands CI runs.
2. `make lint && make test-offline` : the first two jobs locally.
3. `cd app && ./mvnw --batch-mode --no-transfer-progress verify` : the Maven step.
4. `.venv/bin/yamllint -s .github/workflows/ci.yml`.
5. After a push, the Actions tab lists `lint`, `offline`, `stack`.

## 7. Mistakes people make

- A workflow that differs from what you run locally. This one calls the same `make` targets.
- Unpinned third-party actions; major-version tags are used here and should be pinned by hash for production.
- Putting secrets in the file; none are needed.

## 8. Check yourself

1. What starts a workflow?
   *Answer:* The events listed under `on:`.
2. Why does every job check out the code again?
   *Answer:* Each job runs on its own fresh machine.
3. What does `uses:` do?
   *Answer:* Runs a published, reusable action.
4. What turns a check red?
   *Answer:* A step that exits with a non-zero status.
5. How does this workflow stay in step with local work?
   *Answer:* It runs the same `make` targets.

## 9. Further reading

- Workflow syntax: <https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions>.
