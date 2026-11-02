# Docker Compose

## 1. What it is

Docker Compose describes several containers in one YAML file (`docker-compose.yml`) and starts them together with `docker compose up`. It creates a private network where services reach each other by service name, named volumes for data, and passes environment variables.

## 2. Why this repository uses it

The lesson's stack is four cooperating containers: the controller, one agent, a Git server and an artifact store. One command (`make up`) starts them all, and `make down` removes them with their volumes.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `docker-compose.yml` | the four services, their ports, volumes and hardening |
| `scripts/up.sh, down.sh` | `docker compose up --detach --build --wait`, `down --volumes --remove-orphans` |
| `Makefile` | `docker compose config --quiet` in `lint`, `docker compose logs --follow controller` |
| `.env.example` | the variables Compose reads (`CONTROLLER_PORT`, `GIT_PORT`, `SINK_PORT`, two secrets) |

## 4. How it works underneath

- `name: jenkins-controller-as-code` is the **project name**: Compose prefixes the network and volume names with it.
- Each entry under `services:` becomes a container. `build:` builds an image from a folder; `image:` names it. Services share one network and find each other by service name (`http://git-server:8080`).
- `ports: "127.0.0.1:18481:8080"` publishes container port 8080 on the host's loopback address only.
- `volumes:` mounts named volumes (data that survives the container) or `tmpfs` (memory-backed folders).
- `depends_on` with `condition: service_healthy` starts a service only after another one's health check passes.
- `${VAR:-default}` uses a default; `${VAR:?message}` makes Compose refuse to start when the variable is missing. Compose reads `.env` from the project folder automatically.
- Hardening keys: `read_only: true` (read-only root file system), `cap_drop: [ALL]` (no Linux capabilities), `security_opt: ["no-new-privileges:true"]` (a process cannot gain privileges).

## 5. Walkthrough of this repository's use

```yaml
  git-server:
    build:
      context: services/git-server
      args:
        BASE_IMAGE: alpine:3.24.3@sha256:be26...
    environment:
      REPOS: controller-as-code
    ports:
      - "127.0.0.1:${GIT_PORT:-18480}:8080"
    read_only: true
    tmpfs:
      - /tmp:uid=10001,gid=10001
    volumes:
      - git_repos:/srv/git
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```
Build from `services/git-server` passing a build argument (the pinned base). The environment tells the entrypoint which repository to create. The port is published on loopback. The root file system is read-only, so `/tmp` is a memory-backed folder owned by uid 10001 (the unprivileged user), and the repositories live in the named volume `git_repos`. All capabilities are dropped.

```yaml
  publish-sink:
    environment:
      EXPECTED_TOKEN: ${PUBLISH_TOKEN:?run make up, which creates .env}
    ports: ["127.0.0.1:${SINK_PORT:-18482}:8080"]
    read_only: true
    tmpfs: ["/data:uid=10001,gid=10001"]
```
The store requires the token (`:?`): without `.env`, Compose refuses to start rather than run with an empty secret. Uploads go to `/data` in memory and disappear with the container.

```yaml
  controller:
    build: { context: controller }
    image: my-controller:1
    environment:
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?run make up, which creates .env}
      PUBLISH_TOKEN: ${PUBLISH_TOKEN:?run make up, which creates .env}
    ports: ["127.0.0.1:${CONTROLLER_PORT:-18481}:8080"]
    volumes: [jenkins_home:/var/jenkins_home]
    depends_on:
      git-server:
        condition: service_started
```
The two secrets reach the controller only as environment variables; `jenkins.yaml` refers to them as `${ADMIN_PASSWORD}` and `${PUBLISH_TOKEN}`. `jenkins_home` keeps the build history across restarts (the rebuild proof deletes it). The controller is **not** read-only (Jenkins writes in its home).

```yaml
  agent:
    build: { context: agent }
    image: my-agent:1
    environment:
      JENKINS_URL: http://controller:8080
      JENKINS_AGENT_NAME: docker-agent
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?...}
    volumes: [agent_work:/home/jenkins/agent, maven_cache:/home/jenkins/.m2]
    depends_on:
      controller:
        condition: service_healthy
```
The agent reaches the controller at `http://controller:8080` (service name). `agent_work` is its workspace; `maven_cache` keeps downloaded Maven libraries between builds. It waits for the controller's health check.

`volumes:` at the bottom declares `jenkins_home`, `agent_work`, `maven_cache`, `git_repos`.






<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of `docker-compose.yml`

Docker Compose reads one YAML file that describes a set of containers (called **services**) that run together, and starts, networks and stops them with one command. YAML is a text format built from indentation: a line `key: value` is a setting, a line starting with `- ` is one item of a list, and everything indented under a key belongs to that key. Compose puts all services of the file on one private network where each service can reach the others by its service name (for example `http://controller:8080`).

```yaml
# The controller, its agent, the Git server it builds from and the artifact store it publishes to. Credentials come
# from .env (created by `make up`), never from this file.
---
name: jenkins-controller-as-code
```
- Lines 1-2 are comments explaining the file; the credentials are never written here.
- Line 3, `---`, marks the start of a YAML document. It is optional but makes editors and `yamllint` happy.
- Line 4, `name:` sets the **project name**. Compose prefixes the names of the containers, networks and volumes it creates with it, so two projects on the same computer cannot collide.

```yaml
services:
  git-server:
    build:
      context: services/git-server
      args:
        BASE_IMAGE: alpine:3.24.3@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
    environment:
      REPOS: controller-as-code
    ports:
      - "127.0.0.1:${GIT_PORT:-18480}:8080"
    read_only: true
    tmpfs:
      - /tmp:uid=10001,gid=10001
    volumes:
      - git_repos:/srv/git
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```
This is the first service, `git-server`: a tiny web server that hosts Git repositories so the Jenkins job has somewhere to fetch its code from.

- `build:` tells Compose to build the image from a Dockerfile instead of downloading a ready one. `context: services/git-server` is the folder sent to the builder (it contains the Dockerfile).
- `args:` passes build arguments. `BASE_IMAGE` is the starting image. The text after `@sha256:` is a **digest**: a fingerprint of the exact image bytes. Pinning by digest means a later change to the `alpine:3.24.3` tag cannot silently change what you build.
- `environment:` sets environment variables inside the container. `REPOS: controller-as-code` names the repository the entrypoint should create.
- `ports:` publishes a container port on the host. The format is `host-address:host-port:container-port`. `127.0.0.1` means "only this computer can connect". `${GIT_PORT:-18480}` is variable substitution: use the value of `GIT_PORT` from the environment or `.env`, or `18480` if it is unset or empty.
- `read_only: true` mounts the container's root filesystem read-only, so a compromised process cannot write to it.
- `tmpfs:` gives the container a temporary in-memory folder at `/tmp` because the web server still needs somewhere to write. `uid=10001,gid=10001` makes it owned by the unprivileged user the image runs as.
- `volumes:` mounts the named volume `git_repos` at `/srv/git`, so the repositories survive the container being recreated.
- `cap_drop: [ALL]` removes all Linux capabilities (special root-only powers, such as changing file ownership or binding low ports) from the container.
- `security_opt: ["no-new-privileges:true"]` forbids any process inside from gaining more privileges than it started with (for example through a setuid program).

```yaml
  publish-sink:
    build:
      context: services/publish-sink
      args:
        BASE_IMAGE: python:3.13-slim-bookworm@sha256:fa16c23a012723c24eef39cc755a27babbba16b711e5d1e6cf16225ad21637cd
    environment:
      EXPECTED_TOKEN: ${PUBLISH_TOKEN:?run make up, which creates .env}
    ports:
      - "127.0.0.1:${SINK_PORT:-18482}:8080"
    read_only: true
    tmpfs:
      - /data:uid=10001,gid=10001
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```
The artifact store, `publish-sink`, which receives the jar the pipeline publishes. It follows the same pattern: a pinned Python image, a read-only root, a tmpfs at `/data`, no capabilities. The new piece is line 30: `${PUBLISH_TOKEN:?run make up, which creates .env}`. The `:?` form means "if the variable is unset or empty, stop with this message". So `docker compose up` refuses to start without a token, and the token comes from the `.env` file that `make up` creates, never from a file in Git.

```yaml
  controller:
    build:
      context: controller
    image: my-controller:1
    environment:
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?run make up, which creates .env}
      PUBLISH_TOKEN: ${PUBLISH_TOKEN:?run make up, which creates .env}
    ports:
      - "127.0.0.1:${CONTROLLER_PORT:-18481}:8080"
    volumes:
      - jenkins_home:/var/jenkins_home
    depends_on:
      git-server:
        condition: service_started
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```
The Jenkins `controller`.

- `image: my-controller:1` names the image Compose builds, so other tools and the rebuild test can refer to it.
- Two secrets are passed as environment variables: `ADMIN_PASSWORD` and `PUBLISH_TOKEN`, both with the same "must be set" rule. The configuration-as-code file reads them with `${...}`.
- The controller's port 8080 is published on `127.0.0.1:18481` by default.
- `jenkins_home:/var/jenkins_home` is the named volume holding Jenkins' state (job history, builds), the one thing that is allowed to be lost and rebuilt from Git.
- `depends_on` with `condition: service_started` makes Compose start `git-server` before the controller. The controller needs the repository when the first build runs.
- `cap_drop` and `no-new-privileges` repeat the hardening of the other services.

```yaml
  agent:
    build:
      context: agent
    image: my-agent:1
    environment:
      JENKINS_URL: http://controller:8080
      JENKINS_AGENT_NAME: docker-agent
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?run make up, which creates .env}
    volumes:
      - agent_work:/home/jenkins/agent
      - maven_cache:/home/jenkins/.m2
    depends_on:
      controller:
        condition: service_healthy
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```
The build `agent`. `JENKINS_URL` is where to find the controller (by service name), `JENKINS_AGENT_NAME` is the node name to claim, and the admin password lets the entrypoint ask the controller for the agent's connection secret. Two volumes: `agent_work` is the agent's workspace folder and `maven_cache` keeps downloaded Maven libraries between builds so they are not downloaded every time. `condition: service_healthy` is stricter than `service_started`: Compose waits until the controller's `HEALTHCHECK` (from the Dockerfile) reports healthy before starting the agent.

```yaml
volumes:
  jenkins_home:
  agent_work:
  maven_cache:
  git_repos:
```
The top-level `volumes:` block declares the four named volumes. Each name is followed by nothing, which means "create it with default settings". Named volumes are managed by Docker and live until `docker compose down --volumes` deletes them (the `down` script does that).
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `ADMIN_PASSWORD=x PUBLISH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx docker compose config --quiet; echo $?` : `0`.
2. `docker compose ps` (stack up) : four services, `healthy` where a check exists.
3. `docker compose logs --tail 20 agent` : the agent connecting.
4. `docker compose exec agent sh -c 'wget -qO- http://controller:8080/login | head -c 100'` : the controller reachable by service name.
5. `docker compose down --volumes` (via `make down`) : containers, network and volumes removed.

## 7. Mistakes people make

- Putting secrets in the Compose file. Here they come from `.env` through `${VAR:?}`.
- Publishing ports on all interfaces (`"18481:8080"`). Here they bind to `127.0.0.1`.
- Mounting a volume over a folder that holds configuration baked into the image (the reason the configuration file lives outside `JENKINS_HOME`).
- `depends_on` without health conditions: a service starts before its dependency can answer.

## 8. Check yourself

1. How do services find each other?
   *Answer:* By service name on the Compose network.
2. What does `${VAR:?message}` do?
   *Answer:* Stops Compose with that message when the variable is missing.
3. What does `read_only: true` do?
   *Answer:* Makes the container's root file system read-only; writable places are volumes or tmpfs.
4. Why bind ports to `127.0.0.1`?
   *Answer:* So only your machine can reach them.
5. What does `docker compose up --wait` wait for?
   *Answer:* Every service's health check to pass.

## 9. Further reading

- Compose file reference: <https://docs.docker.com/reference/compose-file/>. Docker Compose v2 is used (`docker compose`, not `docker-compose`).
