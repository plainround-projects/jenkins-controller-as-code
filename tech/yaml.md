# YAML

## 1. What it is

YAML is a plain-text format for structured data: lists, key-value maps and values. Most tools of this repository (Jenkins configuration as code, Docker Compose, GitHub Actions, yamllint) read their configuration from YAML files.

## 2. Why this repository uses it

The controller's whole configuration (`jenkins.yaml`), the Compose file, the workflow and the plugin settings are YAML.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `controller/casc/jenkins.yaml` | the controller's configuration as code |
| `docker-compose.yml` | the four services |
| `.github/workflows/ci.yml, .yamllint.yaml` | workflow and linter |

## 4. How it works underneath

- **Indentation is structure.** Two spaces deeper means "inside". Tabs are not allowed.
- A **map** is `key: value`. A **list** item starts with `- `. They nest: a list of maps is very common.
- Scalars (single values) are strings, numbers, `true`/`false` and `null`. `"1"` in quotes is a string; `1` is a number. Tools care about types: a setting that expects a number refuses `"zero"` in quotes.
- `---` starts a new **document** inside one file; Kubernetes files can hold several objects separated by it.
- `|` starts a **block scalar**: the following indented lines are one multi-line string. `{}` is an empty map; `["ALL"]` is a one-line list.
- `# text` is a comment.
- YAML 1.1 reads bare `yes`, `no`, `on`, `off` as booleans. That surprise is called "the Norway problem" (`no` is Norway's country code). Quote them.

## 5. Walkthrough of this repository's use

`controller/casc/jenkins.yaml` shows the YAML features that matter:

```yaml
---
jenkins:
  numExecutors: 0
  mode: EXCLUSIVE
  securityRealm:
    local:
      allowsSignup: false
      users:
        - id: "admin"
          password: "${ADMIN_PASSWORD}"
  nodes:
    - permanent:
        name: "docker-agent"
        labelString: "docker-agent"
        numExecutors: 2
```
* **Nested maps** (`jenkins:` > `securityRealm:` > `local:`) show structure by indentation.
* `numExecutors: 0` is a number; `allowsSignup: false` a boolean; `"admin"` a string.
* `users:` is a **list** of maps (`- id: ...`). `nodes:` is a list whose item has one key, `permanent`, which holds a map.
* `"${ADMIN_PASSWORD}"` is quoted. The configuration-as-code plugin replaces `${...}` from the environment; the quotes keep YAML from reading `$` or `{` as syntax.
* `script: >` (in the job definition) is a **folded block scalar**: the following indented lines are joined into one string, which contains a Groovy script. A `>` joins lines with spaces; `|` would keep the newlines.

`docker-compose.yml` uses `${VAR:-default}` (default value), `${VAR:?message}` (stop with a message if missing), lists of strings (`ports`, `tmpfs`), a one-line list (`cap_drop: [ALL]`) and a top-level `volumes:` map whose keys have empty values (named volumes with default settings).

## 6. Try it yourself

1. `.venv/bin/yamllint -s .` : no output.
2. `.venv/bin/python -c "import yaml; print(yaml.safe_load(open('controller/casc/jenkins.yaml'))['jenkins']['nodes'])"` : the node as a dict.
3. `ADMIN_PASSWORD=x PUBLISH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx docker compose config | head -40` : the Compose file with variables filled in.
4. Delete the leading spaces of one line in a copy and run yamllint : an error names the line.
5. `.venv/bin/pytest tests/unit/test_controller_config.py -q -k compose` : the Compose assertions.

## 7. Mistakes people make

- Wrong indentation moves a key to a different parent without any error.
- Unquoted values that look like something else: `1.10` becomes the number 1.1, `on` becomes true.
- Duplicate keys: the last one silently wins in some parsers. `yamllint` catches it.
- Mixing tabs and spaces. This repository's `.editorconfig` and `yamllint` forbid tabs.

## 8. Check yourself

1. How does YAML show that one key is inside another?
   *Answer:* By deeper indentation with spaces.
2. What is the difference between `1` and `"1"`?
   *Answer:* A number and a string. Kubernetes fields have fixed types.
3. What does `---` do?
   *Answer:* It starts a new document in the same file.
4. What does `|` start?
   *Answer:* A block scalar: the indented lines below are one multi-line string.
5. Why quote `no` or `on`?
   *Answer:* YAML 1.1 parsers read them as booleans.

## 9. Further reading

- YAML 1.2.2 specification: <https://yaml.org/spec/1.2.2/>. Kubernetes reads YAML 1.1-style booleans in some paths, so quote ambiguous words.
