# Jenkins

## 1. What it is

Jenkins is a server that runs **jobs**: it fetches code, runs build and test steps, records the results and can publish artifacts. A **controller** schedules work, stores history and serves the web page and API; **agents** are separate machines or containers that actually run the steps. A **pipeline** is a job described by a script (`Jenkinsfile`) kept in the code repository. **Plugins** add features; almost everything in Jenkins is a plugin.

## 2. Why this repository uses it

The lesson: "the controller is a build artifact". Everything about this controller (version, plugins, security, agents, credentials, the job itself) comes from files in Git, so it can be deleted and rebuilt identically. Jenkins 2.580.1 LTS (JDK 21) is pinned.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `controller/Dockerfile, plugins.txt, plugins.lock.txt, casc/jenkins.yaml` | build the controller from files |
| `agent/` | the build agent |
| `Jenkinsfile` | the pipeline the job runs |
| `tests/support/jenkins.py` | a typed client for the Jenkins HTTP API used by the end-to-end tests |
| `tests/stack/` | tests that trigger the job and check results |
| `scripts/lint-jenkinsfile.sh` | the declarative linter |

## 4. How it works underneath

- **Executors** are slots for running builds. `numExecutors: 0` on the controller means it runs **no** builds itself; builds go to agents. This keeps untrusted build code away from the machine that holds credentials and history.
- An **inbound agent** starts on the build machine and connects to the controller (here over a **WebSocket**, so no extra port). It needs a secret that proves who it is; the entrypoint fetches it from the controller's API using the admin password and then forgets the password.
- **Labels** pick where a stage runs (`agent { label 'docker-agent' }`).
- A **credential** is a stored secret with an id. `withCredentials` makes it available to the steps inside one block, and Jenkins **masks** its value in the build log.
- **CSRF protection**: state-changing requests (POST) need a **crumb**, a token fetched from `/crumbIssuer/api/json` and sent as a header, with the same session cookie.
- The **JENKINS_HOME** folder holds configuration, job definitions and build history. If it is on a volume it survives container recreation.
- The HTTP **API**: append `/api/json` to most pages; `buildWithParameters` starts a build; `consoleText` returns its log; `wfapi/describe` and `wfapi/pendingInputActions` expose pipeline details.

## 5. Walkthrough of this repository's use

### What the controller is built from
1. `controller/Dockerfile`: the pinned base image, the plugin lock, the configuration file (see the Docker and plugin notes).
2. `controller/casc/jenkins.yaml`: security (a local `admin` user with the password from the environment, no sign-up, `loggedInUsersCanDoAnything` with `allowAnonymousRead: false`), `numExecutors: 0`, `mode: EXCLUSIVE` (only run jobs that ask for this node by label), the agent definition, the credential, the location URL and the job (see the JCasC note).

### The agent
```yaml
nodes:
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
          workDirSettings: { disabled: false, failIfWorkDirIsMissing: false, internalDir: "remoting" }
```
A permanent node called `docker-agent`, two executors, working in `/home/jenkins/agent`, `EXCLUSIVE` (only for jobs that name its label), always kept online, launched by the agent connecting inbound over WebSocket. `workDirSettings` keeps the agent's own files under a `remoting` folder in the work directory.

### The pipeline run, in order
`Verify` (on the agent) > `Lint` (checkstyle) > `Build` (package) > `Test` (unit and integration **in parallel**, with `failFast`) > `Coverage` (JaCoCo rule); the jar is **stashed**; an optional `Approve` stage (no agent, so no executor is held while it waits); `Publish` (on an agent) un-stashes the jar and uploads it with the token. Details are in the Jenkinsfile note.

### The HTTP client the tests use (`tests/support/jenkins.py`)
A class `Jenkins(base_url, user, password, opener=...)` built on the standard library `urllib`. `request(method, path, ...)` sends Basic authentication (a header `Authorization: Basic base64(user:password)`), and for POST first fetches a crumb once and sends it as a header. `get_json`, `get_text`, `post`, `trigger(job, parameters)` (reads `nextBuildNumber`, POSTs `build` or `buildWithParameters`, returns the number), `wait_finished(job, number, timeout)` (polls until `building` is false and returns the result), `console`, `timing` (queue and run time from `wfapi/describe`), `pending_inputs` and `approve` (POST the single pending input's `proceedUrl`). The `opener` argument is injectable, so offline tests give it a fake controller that answers canned JSON.

## 6. Try it yourself

1. Open `http://127.0.0.1:18481` (log in as `admin`, password in `.env`) : the dashboard with the job `order-summary`.
2. `curl -s -u admin:$(grep ^ADMIN_PASSWORD= .env | cut -d= -f2) http://127.0.0.1:18481/api/json?tree=numExecutors,mode` : `{"mode":"EXCLUSIVE","numExecutors":0}`.
3. `curl -s -u admin:... http://127.0.0.1:18481/computer/api/json?tree=computer[displayName,offline]` : the agent and the (built-in) controller node.
4. `make lint-jenkinsfile` : `Jenkinsfile successfully validated.`
5. `make run` : triggers the job through the API and asserts the outcome.

## 7. Mistakes people make

- Running builds on the controller. It would give a build the controller's credentials and disk.
- Clicking a configuration into the UI. The next rebuild loses it; change `jenkins.yaml` and rebuild.
- Storing the agent secret in a file. Here it is fetched at start-up and not kept.
- Forgetting the CSRF crumb on API POSTs (you get HTTP 403).

## 8. Check yourself

1. What is the difference between a controller and an agent?
   *Answer:* The controller schedules and stores; agents run the build steps.
2. Why `numExecutors: 0` on the controller?
   *Answer:* To keep build code away from the machine that holds credentials and history.
3. What does `withCredentials` do?
   *Answer:* Makes a stored secret available inside one block and masks it in the log.
4. What is a crumb?
   *Answer:* A CSRF token that Jenkins requires on POST requests.
5. Where does the build history live?
   *Answer:* In `JENKINS_HOME`, here a named volume.

## 9. Further reading

- Jenkins documentation: <https://www.jenkins.io/doc/> (LTS 2.580.x). Remote access API: <https://www.jenkins.io/doc/book/using/remote-access-api/>. Not every statement was re-checked against the 2.580 pages in this session; behavior was taken from the running configuration and the end-to-end tests.
