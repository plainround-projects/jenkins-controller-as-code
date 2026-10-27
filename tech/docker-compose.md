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
