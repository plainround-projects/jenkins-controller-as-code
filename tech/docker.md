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






<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of the four Dockerfiles

A **Dockerfile** is a recipe for building an *image*, a frozen filesystem plus start-up settings. Each instruction is a line starting with an upper-case word. Docker runs them top to bottom, saving the result of each as a *layer*, and reuses layers when nothing before them changed. `ARG` declares a build-time variable; `FROM` chooses the starting image; `COPY` copies files from the build folder into the image; `RUN` runs a command while building; `ENV` sets an environment variable for the running container; `USER` chooses which user the container runs as; `EXPOSE` documents a port; `HEALTHCHECK` is a command Docker runs repeatedly to learn if the container is working; `ENTRYPOINT` and `CMD` define what runs when the container starts.

#### `controller/Dockerfile`

```dockerfile
# The Jenkins controller, built only from files in this repository: a pinned image, an exact plugin list and the
# configuration-as-code file. No setup wizard, no plugin installed by hand.
ARG JENKINS_IMAGE=jenkins/jenkins:2.580.1-lts-jdk21@sha256:a660310e39ade10631f774bacd5219de767dfd08947ea5c32a739b5e5bb382c1
FROM ${JENKINS_IMAGE}

ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/usr/share/jenkins/casc_configs/jenkins.yaml

# plugins.lock.txt names every plugin, transitive ones included, at an exact version (see `make plugins-lock`).
COPY plugins.lock.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# Outside JENKINS_HOME on purpose: a volume mounted there must not hide the configuration.
COPY casc/jenkins.yaml /usr/share/jenkins/casc_configs/jenkins.yaml

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=30 \
  CMD curl -fsS http://localhost:8080/login -o /dev/null || exit 1
```
- Line 3: `ARG JENKINS_IMAGE=...` names the starting image with a default. The part `jenkins/jenkins:2.580.1-lts-jdk21` is a *tag* (Jenkins long-term-support release 2.580.1 on Java 21) and `@sha256:...` pins the exact bytes, so even if someone re-publishes the tag you still get the image you tested.
- Line 4: `FROM ${JENKINS_IMAGE}` starts from it.
- Lines 6-7: `ENV` sets two variables. `JAVA_OPTS=-Djenkins.install.runSetupWizard=false` passes a flag to the Java program that turns off the first-run wizard. `CASC_JENKINS_CONFIG` tells the configuration-as-code plugin where its YAML lives. The trailing backslash continues the instruction on the next line.
- Line 10: copies the plugin lock file to where the image's plugin tool looks. Line 11: `RUN jenkins-plugin-cli --plugin-file ...` downloads every plugin at the listed version *while building*, so the container starts without internet access.
- Line 14: copies the configuration file to a folder outside `/var/jenkins_home` because a volume mounted at `JENKINS_HOME` would hide anything baked in there.
- Lines 16-17: the health check runs every 10 seconds (`--interval`), allows 5 seconds per run (`--timeout`), ignores failures for the first 60 seconds (`--start-period`), and tolerates 30 failures in a row (`--retries`). The command `curl -fsS http://localhost:8080/login -o /dev/null || exit 1` fetches the login page and discards it; failure turns into exit code 1, which Docker reads as "unhealthy". Compose's `service_healthy` waits for this.

#### `agent/Dockerfile`

```dockerfile
# The build agent: the official inbound agent (JDK 21 and git) with an entrypoint that asks the controller for this
# agent's secret, so the secret is never in the repository or the compose file.
ARG AGENT_IMAGE=jenkins/inbound-agent:3391.va_37fa_a_305d6d-8-jdk21@sha256:cd373fdeb8d9388e7deca4195b9fa9b5dd28ba70c9d9ba2b90ba67346f4ab8f8
FROM ${AGENT_IMAGE}

COPY --chmod=0755 entrypoint.sh /usr/local/bin/agent-entrypoint.sh

# The Maven cache volume is mounted here. A new named volume takes the owner of the folder it covers in the image, so
# the folder must exist and belong to the build user, or the Maven wrapper cannot write its download.
USER root
RUN mkdir -p /home/jenkins/.m2 && chown jenkins:jenkins /home/jenkins/.m2
USER jenkins
ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
```
The agent starts from the official Jenkins inbound-agent image (already includes Java 21 and git), pinned by digest. `COPY --chmod=0755` copies the entrypoint script and marks it executable in one step. The `USER root`, `RUN` and second `USER jenkins` lines (with the comment above them) exist because of a fault the first live run exposed: Compose mounts the named volume `maven_cache` at `/home/jenkins/.m2`, and Docker gives a new named volume the owner of the folder it covers *in the image*. If the folder does not exist there, the volume is owned by root and the build user cannot write the Maven wrapper's download (`mkdir: cannot create directory '/home/jenkins/.m2/wrapper': Permission denied`). `mkdir -p` creates the folder and `chown jenkins:jenkins` hands it to the build user; both need root, so the image switches to root for that one line. The last `USER jenkins` makes sure the container does not run as root. `ENTRYPOINT ["..."]` in the *JSON array* form runs the program directly, without a shell wrapping it, so signals reach it.

#### `services/git-server/Dockerfile`

```dockerfile
# A minimal smart-HTTP Git server (nginx + git-http-backend) so the cluster has a repository to watch
# without a GitHub account. Local use only: no authentication, bound to the loopback interface by kind.
ARG BASE_IMAGE=alpine:3.24.3
FROM ${BASE_IMAGE}

RUN apk add --no-cache git git-daemon nginx fcgiwrap tini \
 && adduser -D -u 10001 git \
 && mkdir -p /srv/git && chown git:git /srv/git

COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

USER 10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/entrypoint.sh"]
```
- Line 6: `apk add --no-cache` installs packages on Alpine Linux without keeping the download index: `git`, `git-daemon` (which holds `git-http-backend`), `nginx` (web server), `fcgiwrap` (CGI bridge) and `tini` (a tiny init program that reaps zombie processes and forwards signals). `&&` chains the next commands in the same layer: `adduser -D -u 10001 git` creates an unprivileged user with a fixed numeric id, `mkdir -p /srv/git && chown git:git /srv/git` creates the repository folder owned by that user.
- Lines 10-11 copy the web server configuration and the start-up script.
- Line 13 `USER 10001` runs as that numeric user; the numeric form lets Kubernetes-style tools verify it is not root.
- Line 15's health check uses `wget -q -O /dev/null` against the `/healthz` location of `nginx.conf`.
- Line 16 runs `tini` first, which then starts the entrypoint script (`--` ends tini's own options).

#### `services/publish-sink/Dockerfile`

```dockerfile
ARG BASE_IMAGE=python:3.13-slim-bookworm
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --system --uid 10001 --no-create-home sink
WORKDIR /srv
COPY publish_sink /srv/publish_sink

USER 10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else 1)"
CMD ["python", "-m", "publish_sink"]
```
`PYTHONUNBUFFERED=1` makes Python print logs immediately instead of holding them in a buffer; `PYTHONDONTWRITEBYTECODE=1` stops it writing `.pyc` cache files (useful on a read-only filesystem). `useradd --system --uid 10001 --no-create-home sink` makes the service account. `WORKDIR /srv` sets the current folder for later instructions and for the running container. `COPY publish_sink /srv/publish_sink` copies the Python package. The health check runs a short Python program using only the standard library to fetch `/healthz` and exit 0 only for HTTP status 200. `CMD ["python", "-m", "publish_sink"]` starts the package (its `__main__.py`).
<!-- full-walkthrough:end -->

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
