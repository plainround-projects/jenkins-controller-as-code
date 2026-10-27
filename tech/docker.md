# Docker and the Dockerfile

## 1. What it is

Docker runs programs in **containers**: isolated processes that see their own file system, their own network and their own process list, but share the host's kernel. An **image** is the read-only bundle (files plus start command) a container starts from. A **Dockerfile** is the recipe that builds an image, one instruction per line.

## 2. Why this repository uses it

Four images are built from this repository: the Jenkins controller, the build agent, the Git server and the artifact store. Pinning every base image by digest and running as an unprivileged user are part of the lesson ("the controller is a build artifact").

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `controller/Dockerfile` | Jenkins LTS by tag and digest + plugins from a lock file + the configuration file |
| `agent/Dockerfile, entrypoint.sh` | the official inbound agent image + an entrypoint that fetches its own secret |
| `services/git-server/Dockerfile` | Alpine + git + nginx + fcgiwrap + tini |
| `services/publish-sink/Dockerfile` | Python slim + the store package |
| `docker-compose.yml` | builds and runs them (see the Compose note) |

## 4. How it works underneath

- `docker build` reads the Dockerfile top to bottom. Each instruction (`FROM`, `RUN`, `COPY`...) produces a **layer**, a set of file changes stored by its content hash. Docker re-uses a layer when the instruction and everything before it are unchanged, so put the slow, rarely-changing steps first.
- `FROM` picks the starting image. A **digest** (`image@sha256:...`) pins the exact bytes; a tag such as `1.31.7-alpine` can be re-pushed to point somewhere else.
- `ARG` is a build-time variable; `ENV` is a variable inside the running container.
- `ENTRYPOINT` is the program the container runs; `CMD` gives its default arguments. `USER` sets who runs it. `EXPOSE` only documents a port. `HEALTHCHECK` runs a command periodically and marks the container healthy or not.
- A container is a normal process on the host, started in new Linux **namespaces** (own view of files, network, processes) and limited by **cgroups** (CPU and memory caps).
- Images live in the local Docker store. Compose builds them there and starts containers from them; nothing is pushed to a registry.

## 5. Walkthrough of this repository's use

### `controller/Dockerfile`
```dockerfile
ARG JENKINS_IMAGE=jenkins/jenkins:2.580.1-lts-jdk21@sha256:a660...
FROM ${JENKINS_IMAGE}
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/usr/share/jenkins/casc_configs/jenkins.yaml
COPY plugins.lock.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt
COPY casc/jenkins.yaml /usr/share/jenkins/casc_configs/jenkins.yaml
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=30 \
  CMD curl -fsS http://localhost:8080/login -o /dev/null || exit 1
```
* The base is the long-term-support Jenkins 2.580.1 on JDK 21, pinned by tag **and** digest.
* `JAVA_OPTS="-Djenkins.install.runSetupWizard=false"` turns off the first-run setup wizard (the page that asks you to unlock Jenkins and pick plugins). `CASC_JENKINS_CONFIG` tells the configuration-as-code plugin where its file is.
* The lock file (every plugin and its dependencies at an exact version) is copied as `plugins.txt`, and `jenkins-plugin-cli` downloads and installs exactly those plugins **while the image is built**. No plugin is ever installed by hand later.
* The configuration file is copied **outside** `JENKINS_HOME` on purpose: `JENKINS_HOME` (`/var/jenkins_home`) is a volume at run time, and a volume mounted there would hide a file placed there.
* The health check polls `/login` (up to 30 tries, with a 60 s grace period); Compose's `--wait` and the agent's `depends_on` use it.

### `agent/Dockerfile`
```dockerfile
ARG AGENT_IMAGE=jenkins/inbound-agent:3391.va_37fa_a_305d6d-8-jdk21@sha256:cd37...
FROM ${AGENT_IMAGE}
COPY --chmod=0755 entrypoint.sh /usr/local/bin/agent-entrypoint.sh
USER jenkins
ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
```
`COPY --chmod=0755` copies and makes the script executable in one step. `USER jenkins` runs as the image's unprivileged user. The entrypoint (see the Bash note) obtains the agent's secret from the controller, then starts the agent.

### `services/publish-sink/Dockerfile`
`python:3.13-slim-bookworm` by digest, `PYTHONUNBUFFERED=1` and `PYTHONDONTWRITEBYTECODE=1`, a system user `sink` with uid 10001, `COPY publish_sink /srv/publish_sink`, `USER 10001`, a Python-based `HEALTHCHECK` (the slim image has no `curl`) and `CMD ["python", "-m", "publish_sink"]`.

### `services/git-server/Dockerfile`
Alpine, `RUN apk add --no-cache git git-daemon nginx fcgiwrap tini` (`apk` is Alpine's package manager; `--no-cache` keeps the index out of the image), `adduser -D -u 10001 git` (an unprivileged user with a fixed id), `USER 10001`, and `ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/entrypoint.sh"]`: `tini` is a tiny init process that passes signals on and reaps finished children.

## 6. Try it yourself

1. `docker compose build` (or `make up`) : four images build.
2. `docker image ls my-controller my-agent` : the two Jenkins images.
3. `docker compose exec controller ls /var/jenkins_home/plugins | head` : the installed plugins.
4. `docker compose exec controller env | grep -E 'CASC|JAVA_OPTS'` : the two variables.
5. `docker compose ps` : the `STATUS` column shows `healthy` for the controller.

## 7. Mistakes people make

- **Running as root inside the container.** The images here switch to an unprivileged user and the pods drop all capabilities.
- **A tag that moves.** `latest` can change under you; this repository pins versions and, for base images, digests.
- **Copying secrets into a layer.** A deleted file still exists in an earlier layer. No secret is ever copied into an image here.
- **Forgetting that `RUN` lines each add a layer**, so `apk add` and the clean-up belong in one `RUN` joined with `&&`.
- **Forgetting that a rebuilt image is not used until the container is recreated.** `docker compose up --build` does both.

## 8. Check yourself

1. What is the difference between an image and a container?
   *Answer:* An image is the read-only package; a container is a running process started from it.
2. Why pin a base image by digest?
   *Answer:* A digest names exact bytes and cannot be re-pointed, unlike a tag.
3. What is the difference between `ENTRYPOINT` and `CMD`?
   *Answer:* `ENTRYPOINT` is the program; `CMD` is its default arguments, which a caller can replace.
4. Why put `COPY` of a changing file after `RUN apk add`?
   *Answer:* A changed file invalidates its layer and every layer after it; the slow install stays cached.
5. How does Compose get an image into a running container?
   *Answer:* It builds the image into the local Docker store and creates the container from it (`docker compose up --build`).

## 9. Further reading

- Dockerfile reference: <https://docs.docker.com/reference/dockerfile/>. Engine used while building this repository: Docker 24.0.6 (`docker version`).
