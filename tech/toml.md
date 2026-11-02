# TOML (pyproject.toml)

## 1. What it is

TOML is a simple configuration file format of `[tables]` and `key = value` lines. `pyproject.toml` is the standard file Python tools read for the project's name, dependencies and each tool's settings.

## 2. Why this repository uses it

One file configures pytest, coverage, ruff and mypy and pins the Python dependencies.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `pyproject.toml` | project metadata and tool tables |

## 4. How it works underneath

- `[project]` names the project and lists `dependencies`; `[project.optional-dependencies]` groups extras such as `dev`.
- `[tool.<name>]` tables hold the settings of pytest, coverage, ruff and mypy; each tool finds its own table.
- Values are strings in quotes, numbers, booleans (`true`), and arrays (`["a", "b"]`).
- Versions written `==x.y.z` are exact.

## 5. Walkthrough of this repository's use

The file has the usual shape: `[project]` with `dependencies = ["pyyaml==6.0.3"]`, `[project.optional-dependencies] dev = [...]` (pytest, pytest-cov, ruff, mypy, yamllint, `types-PyYAML`, all exact), and `[tool.*]` tables. What is specific here: `pythonpath = [".", "services/publish-sink"]`; two markers (`stack`, `rebuild`); coverage over `tests/support` and `services/publish-sink/publish_sink`; `line-length = 140`; extra ruff ignores; `files = ["tests", "services/publish-sink", "scripts"]` with `explicit_package_bases` and `mypy_path`. Each table is explained in the note for its tool.

<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: `pyproject.toml`

TOML is a configuration format: `[section]` headers, `key = value` lines, strings in double quotes, lists in square brackets, `true`/`false`. `pyproject.toml` is the standard file where Python projects and their tools keep settings; each tool reads its own `[tool.NAME]` sections. Here it declares the project, the test packages, and the settings of pytest, coverage, ruff and mypy.

```toml
[project]
name = "jenkins-controller-as-code-tests"
version = "0.1.0"
description = "Tests for the controller-as-code project: pipeline scripts, configuration, the artifact store and the running stack"
requires-python = ">=3.12"
dependencies = ["pyyaml==6.0.3"]

[project.optional-dependencies]
dev = ["pytest==9.0.2", "pytest-cov==7.0.0", "ruff==0.14.10", "mypy==1.19.1", "yamllint==1.38.0", "types-PyYAML==6.0.12.20250915"]
```
`[project]` describes the package: `name`, `version`, a `description`, the minimum Python version (`requires-python`) and runtime `dependencies` (PyYAML, pinned to an exact version with `==`, used to parse the YAML configuration in tests). `[project.optional-dependencies]` with a group called `dev` lists the tools needed for development: pytest (tests), pytest-cov (coverage measurement), ruff (lint and format), mypy (type checker), yamllint (YAML style) and the type information package for PyYAML. All are pinned; `requirements-dev.lock` holds the full hash-checked list that `make install` uses.

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = [".", "services/publish-sink"]
addopts = "-ra --strict-markers"
markers = [
  "stack: needs the controller, agent and services from `make up` and drives Jenkins through its API",
  "rebuild: destroys and recreates the controller (slow); run by `make rebuild-proof`",
]
```
`[tool.pytest.ini_options]` configures pytest: `testpaths` is where to look for tests; `pythonpath` adds the repository root and the artifact store's folder to the import path so `import tests...` and `import publish_sink...` work; `addopts` adds options to every run (`-ra` prints a summary of all non-passing tests, `--strict-markers` makes an unregistered marker an error, catching typos); `markers` registers the two labels, with descriptions.

```toml
[tool.coverage.run]
source = ["tests/support", "services/publish-sink/publish_sink"]
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 90
```
`[tool.coverage.run]` says what to measure: the test helpers and the artifact store package; `branch = true` also checks that each side of every `if` ran. `[tool.coverage.report]` prints the missing line numbers and `fail_under = 90` makes the run fail below 90 percent.

```toml
[tool.ruff]
line-length = 140
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "D", "ANN", "S", "PT", "RUF"]
ignore = ["D203", "D213", "D401", "PT018"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S603", "S607", "D", "ANN401", "S105", "S106"]
"tests/support/**" = ["S101", "S603", "S607", "ANN401"]
"services/publish-sink/publish_sink/server.py" = ["S104"]
```
`[tool.ruff]` sets the maximum line length (140) and the Python version to target. `[tool.ruff.lint]` `select` enables rule families by letter: `E` style errors, `F` pyflakes (unused names and similar), `I` import order, `B` likely bugs, `UP` outdated syntax, `SIM` simplifications, `D` docstrings, `ANN` type annotations, `S` security checks, `PT` pytest style, `RUF` ruff's own rules. `ignore` turns off four rules that conflict with the chosen docstring style or are too noisy. `per-file-ignores` relaxes rules by path pattern: in tests, `assert` (S101), subprocess calls (S603, S607), docstrings (D) and fake passwords (S105, S106) are allowed; the web server may bind to all interfaces (S104).

```toml
[tool.mypy]
python_version = "3.12"
strict = true
files = ["tests", "services/publish-sink", "scripts"]
explicit_package_bases = true
mypy_path = "services/publish-sink:scripts:."
```
`[tool.mypy]` runs the type checker in `strict` mode on three folders. `explicit_package_bases` and `mypy_path` tell it where each package's root is, so `import publish_sink` resolves to the right folder.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['tool']['pytest']['ini_options']['markers'])"` : the two markers.
2. `grep -n '^\[' pyproject.toml` : every table.
3. Set `fail_under = 99` and run `make test-offline` : the coverage gate fails.
4. `.venv/bin/ruff check --show-settings . | head`.
5. `.venv/bin/pytest --markers | head` : the registered markers.

## 7. Mistakes people make

- Unquoted strings, or YAML-style `key: value`.
- Putting a setting in the wrong `[tool.*]` table, where the tool never reads it.

## 8. Check yourself

1. What is a TOML table?
   *Answer:* A `[name]` heading that groups the keys below it.
2. Where do tool settings go in `pyproject.toml`?
   *Answer:* Under `[tool.<toolname>]`.
3. What does `==6.0.3` mean?
   *Answer:* Exactly that version.
4. How is a list written?
   *Answer:* In square brackets with quoted items.
5. Which file lists the project's dependencies?
   *Answer:* `pyproject.toml`, under `[project]`.

## 9. Further reading

- TOML 1.0: <https://toml.io/en/v1.0.0>. pyproject.toml guide: <https://packaging.python.org/en/latest/guides/writing-pyproject-toml/>.
