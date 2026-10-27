# Jenkins plugins and the plugin lock

## 1. What it is

Jenkins gets features from **plugins**. A plugin has dependencies on other plugins. A **plugin list** with exact versions, including all transitive dependencies, is a **lock file**. `jenkins-plugin-cli` is the command-line tool that installs plugins from such a list into an image.

## 2. Why this repository uses it

A controller that is "a build artifact" must install the same plugins every time. The Dockerfile installs from `plugins.lock.txt` (80 plugins at exact versions); the short list people edit is `plugins.txt` (12 plugins).

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `controller/plugins.txt` | the 12 plugins this controller is built for, each at an exact version |
| `controller/plugins.lock.txt` | the resolved list of 80 plugins (generated) |
| `scripts/plugins_lock.py` | resolves `plugins.txt` into the lock using the Jenkins update center, without Docker |
| `controller/Dockerfile` | `jenkins-plugin-cli --plugin-file ...` |
| `Makefile (`plugins-lock`)` | runs the resolver |
| `tests/unit/` | tests that every plugin is pinned to an exact version and that the lock contains each top-level plugin |

## 4. How it works underneath

- A line is `name:version`. The update center (a JSON catalogue at `updates.jenkins.io`) lists, for each plugin, its version, its dependencies and the Jenkins core version it needs.
- A dependency can be **optional**; optional ones are not installed.
- The resolver adds, for every plugin, each required dependency at the newest version the update center offers **for the pinned Jenkins line** (`dynamic-stable-2.580.1`), and repeats until nothing is missing. The result lists each plugin once at one version.
- Installing from the lock means `jenkins-plugin-cli` has nothing left to resolve at build time, so the image is the same on every build.

## 5. Walkthrough of this repository's use

`controller/plugins.txt` (comments omitted):
```
configuration-as-code:2136.veb_3a_554550b_f
workflow-aggregator:608.v67378e9d3db_1
git:5.11.0
credentials-binding:728.v902a_273b_8947
junit:1442.vb_b_a_467df2767
timestamper:1.30
ws-cleanup:0.49
matrix-auth:3.3
job-dsl:3732.v9a_c49a_61a_313
pipeline-stage-view:2.41
pipeline-input-step:560.v56198a_642157
build-timeout:1.41
```
In order: configuration as code; the whole Pipeline suite (`workflow-aggregator`); Git; credentials binding (`withCredentials`); JUnit test results; timestamps in logs; workspace cleanup; matrix authorization; Job DSL (the `jobs:` section); the Pipeline stage view (and the `wfapi` API); the `input` step; build timeouts.

`scripts/plugins_lock.py`:
```python
CORE = re.search(r"jenkins/jenkins:(\d+\.\d+\.\d+)-lts", (ROOT / "controller" / "Dockerfile").read_text())
UPDATE_CENTER = f"https://updates.jenkins.io/dynamic-stable-{CORE.group(1)}/update-center.actual.json"
```
The Jenkins version is read from the Dockerfile, so the lock always matches the pinned core. `fetch_catalog()` downloads the catalogue with `urllib` and returns its `plugins` table. `top_level(path)` reads `name:version` lines, ignoring blanks and comments, into a dict.

```python
def resolve(requested, catalog):
    lock = dict(requested)
    pending = list(requested)
    while pending:
        name = pending.pop()
        for dependency in catalog[name].get("dependencies", []):
            needed = dependency["name"]
            if dependency.get("optional") or needed == "" or needed in lock or needed not in catalog:
                continue
            lock[needed] = catalog[needed]["version"]
            pending.append(needed)
    return lock
```
A work-list algorithm: take a plugin, look at its dependencies, add every required one not already present at the catalogue's newest version, and queue it so *its* dependencies are examined too. The requested plugins keep the versions written in `plugins.txt`. `main` writes a header comment and the lines **sorted as full strings**; with `--check` it compares instead of writing (exit 1 on a difference). A one-off run of `jenkins-plugin-cli` in Docker produced the same 80-plugin set; the Python resolver does it in seconds without Docker.

## 6. Try it yourself

1. `wc -l controller/plugins.txt controller/plugins.lock.txt` : 12 lines of entries versus 80 plus a header.
2. `python3 scripts/plugins_lock.py --check; echo $?` (needs network) : `0` when the lock is current.
3. `.venv/bin/pytest tests/unit/test_controller_config.py -q -k plugin` : tests that every plugin is pinned and the lock contains each top-level plugin.
4. `docker compose exec controller jenkins-plugin-cli --list | head` : the installed plugins and versions.
5. Open *Manage Jenkins > Plugins > Installed* : the same list in the UI.

## 7. Mistakes people make

- Pinning only the top-level plugins: a new transitive dependency version then changes the image on the next build.
- Updating one plugin by clicking *Update* in the UI: it works until the next rebuild and then silently reverts.
- Mixing plugin versions made for different Jenkins cores. The lock uses the update center of the pinned line.

## 8. Check yourself

1. What is in a lock file that is not in the plugin list?
   *Answer:* Every transitive dependency at an exact version.
2. Why resolve against `dynamic-stable-2.580.1`?
   *Answer:* So every plugin version is compatible with the pinned Jenkins.
3. What does `jenkins-plugin-cli` do?
   *Answer:* Installs plugins from a list into the image at build time.
4. Are optional dependencies installed?
   *Answer:* No.
5. What does `--check` do?
   *Answer:* Compares the lock with what the resolver would write and exits 1 on a difference.

## 9. Further reading

- Plugin installation tool: <https://github.com/jenkinsci/plugin-installation-manager-tool>. Update center: <https://updates.jenkins.io/>.
