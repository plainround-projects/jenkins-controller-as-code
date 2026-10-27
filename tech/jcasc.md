# Jenkins Configuration as Code (JCasC)

## 1. What it is

The Configuration as Code plugin lets you describe a Jenkins controller in a YAML file instead of clicking through the web UI. At start-up the plugin reads the file and applies it: security, nodes, credentials, system settings and even jobs.

## 2. Why this repository uses it

This file is the heart of the lesson: if the whole controller is a file in Git, then the controller can be deleted and recreated, reviewed in a pull request and compared with a previous version. The plugin is pinned (`configuration-as-code`) in the plugin list.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `controller/casc/jenkins.yaml` | the file |
| `controller/Dockerfile` | `CASC_JENKINS_CONFIG` points at it and it is copied into the image |
| `tests/unit/` | configuration tests read it as data |
| `tests/stack/test_rebuild.py` | the rebuild proof compares the configuration before and after |

## 4. How it works underneath

- The top-level keys match parts of Jenkins: `jenkins:` (core settings, security, nodes), `credentials:` (the credential store), `unclassified:` (settings of plugins and the "location"), `jobs:` (job definitions; needs the Job DSL plugin) and others.
- `${NAME}` is replaced by an environment variable of the Jenkins process. A missing variable stops Jenkins from starting, which is good: a secret is never silently empty. `${NAME:-default}` provides a default.
- On start-up the plugin applies the file; applying it again later gives the same state.
- The `jobs:` section with `- script: >` runs a **Job DSL** script that creates a pipeline job.

## 5. Walkthrough of this repository's use

```yaml
jenkins:
  systemMessage: "Controller as code: change controller/casc/jenkins.yaml in Git, not this page."
  numExecutors: 0
  mode: EXCLUSIVE
  quietPeriod: 0
```
A banner shown at the top of every page; no executors on the controller; the controller only runs jobs that ask for it by label (and none do); no waiting period before a build starts (`quietPeriod: 0`), so the lesson's runs begin at once.

```yaml
  securityRealm:
    local:
      allowsSignup: false
      users:
        - id: "admin"
          password: "${ADMIN_PASSWORD}"
  authorizationStrategy:
    loggedInUsersCanDoAnything:
      allowAnonymousRead: false
```
The **realm** answers "who are you": a built-in user database with one user, no self sign-up, the password from the environment. The **authorization strategy** answers "what may you do": a logged-in user may do anything, and anonymous users may read nothing.

```yaml
credentials:
  system:
    domainCredentials:
      - credentials:
          - string:
              id: "publish-token"
              scope: GLOBAL
              description: "Token the publish step presents to the artifact store"
              secret: "${PUBLISH_TOKEN}"
```
A "secret text" credential. The **id and type live in Git**; only the **value** comes from the environment. The Jenkinsfile asks for it by id.

```yaml
unclassified:
  location:
    url: "http://localhost:18481/"
    adminAddress: "admin@example.invalid"
```
The URL Jenkins uses in links it generates.

```yaml
jobs:
  - script: >
      pipelineJob('order-summary') {
        parameters { booleanParam('REQUIRE_APPROVAL', false, '...') ... }
        definition {
          cpsScm {
            scm { git { remote { url('http://git-server:8080/controller-as-code.git') } branches('*/main') } }
            scriptPath('Jenkinsfile')
            lightweight(true)
          }
        }
      }
```
A Job DSL (Groovy) script creates a pipeline job named `order-summary` with three boolean parameters, whose pipeline definition is read from the `Jenkinsfile` of the `main` branch in the Git server (`cpsScm` = "pipeline script from SCM"). The Jenkinsfile declares the same parameters; the job also declares them so that the **first** build can be started with parameters.

The agent is defined here as well (see the Jenkins note). The whole file has **no secret value**: the offline test asserts that passwords and tokens appear only as `${...}` references.

## 6. Try it yourself

1. `grep -n '\${' controller/casc/jenkins.yaml` : the only dynamic values: `ADMIN_PASSWORD` and `PUBLISH_TOKEN`.
2. `.venv/bin/pytest tests/unit/test_controller_config.py -q` : the configuration assertions.
3. In the running controller open *Manage Jenkins > Configuration as Code* : the file's content, applied.
4. `docker compose logs controller | grep -i 'configuration as code'` : the plugin's start-up lines.
5. `make rebuild-proof` : delete the controller and its volume, start again, compare the configuration (slow).

## 7. Mistakes people make

- Editing settings in the UI: they are lost at the next rebuild and make the live controller differ from Git.
- Putting a secret value in the file. The reference `${NAME}` keeps the value out of Git.
- Forgetting that plugin settings need their plugin installed: the file lists keys from plugins that must be in the lock file.

## 8. Check yourself

1. What does JCasC replace?
   *Answer:* Clicking through the Jenkins web UI to configure the controller.
2. How do secrets reach the file?
   *Answer:* As `${NAME}` references to environment variables.
3. What happens if a referenced variable is missing?
   *Answer:* Jenkins refuses to start.
4. Which key sets the number of builds the controller itself runs?
   *Answer:* `jenkins.numExecutors`.
5. What creates the job?
   *Answer:* A Job DSL script under `jobs:`.

## 9. Further reading

- Configuration as Code plugin: <https://www.jenkins.io/projects/jcasc/> and the plugin's documentation on GitHub (<https://github.com/jenkinsci/configuration-as-code-plugin>). Version pinned in `controller/plugins.txt`. Not re-checked page by page against that version in this session.
