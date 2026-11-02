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







<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of `controller/casc/jenkins.yaml`

JCasC ("Jenkins Configuration as Code") is a Jenkins plugin that reads a YAML file at startup and applies it as if someone had clicked through all the settings pages. The file is plain YAML (see `yaml.md`). Text like `${ADMIN_PASSWORD}` is replaced by the value of that environment variable; if the variable is missing, Jenkins refuses to start rather than run with a blank password.

```yaml
---
# Everything about this controller that is configuration. Values in ${...} come from the container's environment
# (docker-compose.yml passes them from .env); a missing variable stops Jenkins from starting.
jenkins:
  systemMessage: "Controller as code: change controller/casc/jenkins.yaml in Git, not this page."
  # No builds on the controller: every build runs on an agent.
  numExecutors: 0
  mode: EXCLUSIVE
  quietPeriod: 0
```
- `---` starts the YAML document; lines 2-3 are comments.
- `jenkins:` is the top-level section for core Jenkins settings.
- `systemMessage` is the banner shown on the home page.
- `numExecutors: 0` means the controller itself runs no builds. An executor is one slot for running a build. With zero on the controller, all builds go to an agent; builds on the controller would be a security risk because the build code could read the controller's files.
- `mode: EXCLUSIVE` means "only run jobs that explicitly ask for this node's label".
- `quietPeriod: 0` starts a triggered build immediately instead of waiting a few seconds.

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
`securityRealm` decides *who users are*. `local` uses Jenkins' own user database. `allowsSignup: false` removes the "create an account" link. `users` lists the one user, `admin`, whose password is the environment variable. `authorizationStrategy` decides *what users may do*: `loggedInUsersCanDoAnything` lets any logged-in user do everything, and `allowAnonymousRead: false` shows nothing to people who are not logged in.

```yaml
  nodes:
    # The container agent (agent/Dockerfile). It connects to the controller over a WebSocket; its secret is read by
    # the agent's entrypoint from the controller's API, so no agent secret is stored anywhere.
    - permanent:
        name: "docker-agent"
        labelString: "docker-agent"
        numExecutors: 2
        remoteFS: "/home/jenkins/agent"
        mode: EXCLUSIVE
        retentionStrategy: "always"
        launcher:
          inbound:
            webSocket: true
            workDirSettings:
              disabled: false
              failIfWorkDirIsMissing: false
              internalDir: "remoting"
```
`nodes` declares machines that run builds. `- permanent:` is one item of the list: a node that always exists. Its `name` and `labelString` are both `docker-agent`; the Jenkinsfile asks for that label. `numExecutors: 2` lets two builds run on it at once (the parallel Unit and Integration stages need two). `remoteFS` is the folder on the agent where workspaces live. `retentionStrategy: "always"` keeps the node online. The `launcher` says how the agent connects: `inbound` means the agent starts the connection to the controller (not the other way), `webSocket: true` makes it use an ordinary HTTP WebSocket instead of a separate TCP port. `workDirSettings` configures the agent's "remoting" working directory: it is enabled (`disabled: false`), a missing folder is not an error, and `internalDir: "remoting"` is the folder name used for internal files.

```yaml
credentials:
  system:
    domainCredentials:
      - credentials:
          # The id and type live in Git; only the secret value comes from the environment.
          - string:
              id: "publish-token"
              scope: GLOBAL
              description: "Token the publish step presents to the artifact store"
              secret: "${PUBLISH_TOKEN}"
```
`credentials` creates entries in Jenkins' secret store. `system` is the global store, `domainCredentials` groups credentials by domain, and `- credentials:` begins that group's list. The entry is of type `string` (a secret text): its `id` (what the Jenkinsfile asks for), `scope: GLOBAL` (usable by any job), a `description`, and the `secret`, read from the `PUBLISH_TOKEN` environment variable. The id and type are in Git; the value never is.

```yaml
unclassified:
  location:
    url: "http://localhost:18481/"
    adminAddress: "admin@example.invalid"
```
`unclassified` is where JCasC puts plugin settings that do not fit anywhere else. `location.url` is the address Jenkins uses in links; `adminAddress` is the reply-to address for any mail Jenkins sends (`.invalid` is a reserved domain that can never exist).

```yaml
jobs:
  - script: >
      pipelineJob('order-summary') {
        description('Builds, tests and publishes the order-summary project from the Jenkinsfile in Git')
        parameters {
          booleanParam('REQUIRE_APPROVAL', false, 'Hold the publish step until a person approves it')
          booleanParam('ECHO_TOKEN', false, 'Make the publish step echo its token, to show that the log masks it')
          booleanParam('BREAK_A_TEST', false, 'Make one unit test fail, to show how a failing test is reported')
        }
        definition {
          cpsScm {
            scm {
              git {
                remote { url('http://git-server:8080/controller-as-code.git') }
                branches('*/main')
              }
            }
            scriptPath('Jenkinsfile')
            lightweight(true)
          }
        }
      }
```
`jobs:` is handled by the Job DSL plugin: each item with `script:` is a Groovy program that creates jobs. The `>` after `script:` begins a YAML "folded" text block, a multi-line string written with indentation. The program calls `pipelineJob('order-summary')` which defines a pipeline job. `parameters { booleanParam(...) }` mirrors the three parameters in the Jenkinsfile so the job form shows them from the first run. `definition { cpsScm { ... } }` says the pipeline script comes from source control ("CPS" is the Jenkins engine that runs pipeline Groovy, and `cpsScm` means "load the script from SCM"). `scm { git { ... } }` names the repository: `remote { url(...) }` is the Git server container's address (reached by service name), and `branches('*/main')` selects the main branch. `scriptPath('Jenkinsfile')` is the file to load. `lightweight(true)` fetches just that one file instead of cloning the whole repository for the definition.
<!-- full-walkthrough:end -->

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
