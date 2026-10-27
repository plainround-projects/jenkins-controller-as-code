# PyYAML

## 1. What it is

PyYAML is a Python library that turns YAML text into Python dictionaries and lists (`yaml.safe_load`) and back.

## 2. Why this repository uses it

The offline tests read the controller configuration (`jenkins.yaml`), the Compose file and the Jenkinsfile's structure as data and assert on them.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `tests/unit/ (configuration and compose tests)` | load `controller/casc/jenkins.yaml` and `docker-compose.yml` with `yaml.safe_load` |
| `pyproject.toml, requirements.lock` | pinned at 6.0.3 |

## 4. How it works underneath

- `yaml.safe_load(text)` returns the first document as nested dicts and lists. `safe_load_all` yields one object per `---` document.
- `safe_` means it builds only plain data. The non-safe `yaml.load` can create arbitrary Python objects from a tag, which is a security risk with untrusted files.
- Numbers come back as `int`, quoted values as `str`, `true` as `True`.

## 5. Walkthrough of this repository's use

The configuration test loads `controller/casc/jenkins.yaml` and asserts facts about it as ordinary Python: `numExecutors` is `0`; no password or token value is written in the file (every secret is a `${...}` reference); the one node is labelled `docker-agent`; the job definition points at the Git server and the `Jenkinsfile`. The Compose test loads `docker-compose.yml` and asserts that every base image is pinned and that credentials come from the environment rather than being written in the file. Because the data is plain dicts, an assertion is a one-line expression over the loaded structure.

## 6. Try it yourself

1. `.venv/bin/python -c "import yaml; d=yaml.safe_load(open('controller/casc/jenkins.yaml')); print(d['jenkins']['numExecutors'])"` : `0`.
2. `.venv/bin/python -c "import yaml; print(list(yaml.safe_load(open('docker-compose.yml'))['services']))"` : `['git-server', 'publish-sink', 'controller', 'agent']`.
3. `.venv/bin/pytest tests/unit/test_controller_config.py -q` : the configuration tests.
4. `.venv/bin/pip show pyyaml | head -2` : 6.0.3.
5. `.venv/bin/python -c "import yaml; print(yaml.safe_load('password: \"\${ADMIN_PASSWORD}\"'))"` : the placeholder stays a plain string.

## 7. Mistakes people make

- Using `yaml.load` on files you did not write.
- Forgetting that `safe_load` reads only the first document of a multi-document file.
- Expecting YAML 1.2 rules: PyYAML follows YAML 1.1.

## 8. Check yourself

1. What is the difference between `safe_load` and `safe_load_all`?
   *Answer:* One reads the first document; the other yields every document.
2. Why prefer `safe_load` over `load`?
   *Answer:* It cannot build arbitrary Python objects from a file.
3. What does `no` become in PyYAML?
   *Answer:* `False`.
4. What type is a quoted `"1"`?
   *Answer:* A string.
5. Why do tests load YAML as data?
   *Answer:* To assert on facts without starting any containers.

## 9. Further reading

- PyYAML: <https://pyyaml.org/wiki/PyYAMLDocumentation> (6.0.3).
