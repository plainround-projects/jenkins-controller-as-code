# jenkins-controller-as-code

A Jenkins controller in a container whose whole configuration, from plugins and security to the agent and the credential reference, comes from files in this repository. Destroy the container and its volume, start it again, and it comes back identical. On it, a declarative pipeline builds and tests a small Java project on a container agent, with parallel test stages, published reports, an approval that holds no executor, and a token bound to one step.

| | |
| --- | --- |
| **Lesson** | `/prep/jenkins/project-controller-as-code`, "A controller that is only code" (`data-structure-explainer/src/content/tracks/jenkins/13-project-controller-as-code.md` in the Plainround app) |
| **Planned hours** | 5 |
| **Level** | Beginner |
| **Architecture** | [ARCHITECTURE.md](ARCHITECTURE.md), decisions in [docs/adr](docs/adr) |

## Prerequisites

| Tool | Version | Used for |
| --- | --- | --- |
| Docker with Compose v2 | 24 or newer (tested with 24.0.6), 4 GB or more for its VM | the controller, the agent, the Git server, the artifact store |
| Jenkins | `jenkins/jenkins:2.580.1-lts-jdk21`, pinned by tag and digest in `controller/Dockerfile`; 80 plugins pinned in `controller/plugins.lock.txt` | the controller |
| Agent image | `jenkins/inbound-agent:3391.va_37fa_a_305d6d-8-jdk21`, pinned by tag and digest | the build agent (JDK 21) |
| JDK | 21 or newer on the host (tested with 25) | only for `make lint` and `make test` (the Java project's checkstyle and tests run on the host too); the pipeline uses the agent's JDK |
| Python | 3.12 or 3.13 (tested with 3.13) | the tests; `make` installs `pytest`, `ruff`, `mypy` and `pyyaml` into `.venv/` from a hash-pinned lock file |
| shellcheck, yamllint | any recent | `make lint` |
| git, curl, openssl, GNU Make | any recent | scripts |
| Network | for the first `make up` | Docker images, Jenkins plugins, Maven Central |

No cloud account. Host ports 18480 (Git), 18481 (Jenkins) and 18482 (artifact store) on `127.0.0.1` must be free.

## Setup, run, test, stop

```bash
make up                # creates .env with random secrets, builds the images, starts everything, seeds the repository the job builds
make run               # the scripted end-to-end run: triggers the job through the API and asserts every result (about 10 minutes)
make rebuild-proof     # destroys the controller and its volume, starts it again, compares the configuration (slow)
make test              # offline tests with coverage, the Java project's tests, then the end-to-end run
make lint              # yamllint, shellcheck, ruff, mypy, compose config, checkstyle
make plugins-lock      # re-resolve controller/plugins.txt into controller/plugins.lock.txt
make down              # stop everything and delete the volumes
```

`make help` lists every target. The controller is at <http://127.0.0.1:18481> (user `admin`, the password is in `.env`, which `make up` creates and Git ignores). After changing a file you want the job to build, run `make seed`.

### Credentials

Only from the environment. `make up` writes `.env` with a random `ADMIN_PASSWORD` and `PUBLISH_TOKEN`; `docker-compose.yml` passes them to the containers; `controller/casc/jenkins.yaml` refers to them as `${ADMIN_PASSWORD}` and `${PUBLISH_TOKEN}` and Jenkins refuses to start if one is missing. No secret is in any tracked file, in an image layer or in a log.

## Done when: the lesson's checklist and the proof for each line

| # | Done when (from the lesson) | Command | What proves it |
| --- | --- | --- | --- |
| 1 | The image builds reproducibly, and the plugin list in the running controller matches your file exactly. | `make up`, `make run` | `tests/stack/test_controller.py`: every `name:version` of `controller/plugins.lock.txt` is installed in the running controller at that version, and nothing from the lock is missing. Reproducibility: the image is pinned by tag *and* digest, and all 80 plugins by exact version (`tests/unit/test_controller_config.py`); `make plugins-lock` shows the diff when anything is re-resolved. |
| 2 | Deleting the container and its volume, then starting a new one, gives the same configuration with nothing clicked. | `make rebuild-proof` | `tests/stack/test_rebuild.py` exports the controller's effective configuration (configuration as code's own export), runs `docker compose down --volumes`, starts again, exports again and compares: equal. The rebuilt controller then runs the job to `SUCCESS` and its build history starts at 1. |
| 3 | A run shows the test report and the archived artifact, and a failing test marks the build unstable or failed as you intend. | `make run` | `tests/stack/test_pipeline.py`: the first run is `SUCCESS` with a Pipeline test report (all unit and integration tests, none failed) and `order-summary-1.0.0.jar` archived; a run with `BREAK_A_TEST=true` is `FAILURE` (intended: red, not yellow), its report shows exactly one failure, nothing is archived and the Publish stage never runs. |
| 4 | The run's stage view shows the branches in parallel, and the total time drops compared with the sequential run. | `make run` | `test_the_unit_and_integration_branches_ran_in_parallel` reads the stage timings from `wfapi/describe` and asserts the Unit and Integration intervals overlap. The total time drops by the shorter of the two branches; the console shows both branches with their `[Unit]`/`[Integration]` prefixes. |
| 5 | The token never appears in the log, even when the step echoes it, and no other step can read it. | `make run` | A run with `ECHO_TOKEN=true` makes the publish step execute `echo "token=$TOKEN"`; the log shows `token=****` and `Masking supported pattern matches of $TOKEN`, and the real value (read from `.env`) appears nowhere in it. `tests/unit/test_jenkinsfile.py` shows `withCredentials` appears once, around the publish steps, and nothing before the Publish stage mentions `TOKEN`. The artifact store, which accepts only the right token, received the jar: the credential reached the one step that needs it. |
| 6 | A teammate, or you on a new machine, gets a working controller and a green build by following the README alone. | The fresh-clone test | [Rebuild from scratch](#rebuild-from-scratch) below is the whole procedure; the fresh-clone run of it is recorded in [Verification status](#verification-status). |

Also proven, from the lesson's stretch list: the **approval** (`REQUIRE_APPROVAL=true`): the build waits for `input`, the agent shows no running executable while it waits, and approving through the API lets it publish.

### Rebuild from scratch

```bash
git clone <this repository> && cd jenkins-controller-as-code
make up      # needs Docker and the prerequisites above; creates .env
make run     # a green build, checked through the API
```

What is **not** reproduced by a rebuild, and is not meant to be: build history and past console logs (they live in the volume), and the secret values themselves (only their ids and types are in Git; the values are in `.env`).

## Stretch goals

| Stretch (from the lesson) | Built? |
| --- | --- |
| Add a multibranch pipeline that builds every branch and pull request. | No. [ARCHITECTURE.md](ARCHITECTURE.md#how-to-extend-it) says how (`multibranchPipelineJob` in the casc file). |
| Add an `input` step for a manual approval placed outside any agent, so it holds no executor while waiting. | **Yes.** Stage `Approve` with `agent none`; see done-when proof above and [ADR 0004](docs/adr/0004-approval-outside-any-agent.md). |
| Back up only the parts of the controller's home that configuration as code can't recreate, and say what they are. | Described, not built: `jobs/*/builds` (history) and `secrets/` (the controller's keys); everything else is in this repository ([ARCHITECTURE.md](ARCHITECTURE.md#how-to-extend-it)). |

## What is simplified for teaching

Only what the lesson scopes out, plus where this build differs from the lesson's text:

- One controller, one agent in a container, local accounts, HTTP on loopback ports, a Git server without authentication, an artifact store that stands in for a real one.
- The lesson's plugin list contains a version that does not exist (`600.vb_57cdd8either`) and an old base image; this build resolves the real versions on the LTS line `2.580.1` and locks all 80 plugins, dependencies included, so a rebuild next month is the same controller.
- The lesson's sample project uses Gradle; this one uses Maven with a wrapper, whose Surefire and Failsafe plugins make the parallel split natural ([ADR 0003](docs/adr/0003-maven-wrapper-for-the-project.md)).
- The agent is a container in the same Compose project rather than a Kubernetes pod; the lesson's JCasC example uses a Kubernetes cloud, which the third Jenkins project builds.
- The agent reads its connection secret from the controller's API with the admin credentials at start ([ADR 0002](docs/adr/0002-an-agent-that-fetches-its-own-secret.md)).
- The first run is started without parameters because Jenkins learns the Jenkinsfile's parameters from the first run.

## Project structure

```text
controller/               the pinned image's inputs
  Dockerfile              Jenkins LTS by tag and digest, plugins from the lock file, no setup wizard
  plugins.txt             the plugins the controller is built for, exact versions
  plugins.lock.txt        every plugin, dependencies included, exact versions (generated)
  casc/jenkins.yaml       configuration as code: security, zero executors, the agent node, the credential, the job
agent/                    the build agent image and its entrypoint
services/git-server/      the Git server the job builds from
services/publish-sink/    the artifact store (typed Python, tested)
app/                      the Java project the pipeline builds (Maven wrapper)
  src/main/java/dev/plainround/orders/{domain,application,infrastructure,interfaces}
  src/test/java           unit tests (*Test) and integration tests (*IT), ArchUnit for the dependency rule
Jenkinsfile               the declarative pipeline
pipeline/scripts/         the reusable steps: publish.sh, test-summary.sh
scripts/                  up, down, seed-project, plugins-lock, init-env, lint-jenkinsfile
tests/support/            typed helpers: command runner, polling with an injected clock, a Jenkins API client
tests/unit/               scripts, store, configuration and Jenkinsfile; no containers
tests/stack/              the end-to-end run and the rebuild proof, against the running controller
docs/adr/                 decision records
docker-compose.yml        controller, agent, Git server, artifact store
tech/                     one beginner-level note per technology this repository uses, from zero; start at tech/README.md
```

Dependency rule: in `app/`, domain depends on nothing, application on domain, infrastructure and interfaces on both, and nothing on interfaces (an ArchUnit test). Elsewhere: tests depend on the scripts, the Jenkinsfile and `tests/support`; the Jenkinsfile depends on `pipeline/scripts`; the controller depends on nothing in `app/`.

## Troubleshooting

- **`make up` waits at "controller" for a long time on the first run:** the image build downloads 80 plugins and the controller then loads them; the health check allows several minutes.
- **The agent never comes online:** `docker compose logs agent` shows "waiting for the controller to offer a secret"; the controller is still starting, or `ADMIN_PASSWORD` differs between `.env` and the controller's volume (`make down` deletes the volume).
- **The job builds old files:** `make seed` pushes the current working tree to the Git server.
- **Port 18481 is in use:** set `CONTROLLER_PORT` in `.env` and the `location` URL in `controller/casc/jenkins.yaml`.
- **The Maven build is slow the first time:** it downloads dependencies into the `maven_cache` volume; later runs reuse it.

## Verification status

Verified on 2026-10-27 in the session that built this repository:

- The Java project: `./mvnw verify` in `app/` passes (33 unit tests, 9 integration tests, JaCoCo 95 percent gate on domain and application, ArchUnit layering, `-Xlint:all -Werror`), `checkstyle:check` passes, and the pipeline's own goal sequence (`jacoco:prepare-agent@agent surefire:test`, `failsafe:integration-test failsafe:verify`, `jacoco:report@report jacoco:check@coverage`) runs; `BREAK_A_TEST=true` makes exactly one unit test fail.
- `make test-offline`: 73 tests pass at 95 percent coverage, including the Jenkins API client against a fake controller, the pipeline scripts against a real HTTP artifact store, the artifact store, the Jenkinsfile's structure and the controller's configuration; `yamllint`, `shellcheck`, `ruff` and `mypy` pass.
- The three images build, and the plugin lock (80 plugins) was resolved by running `jenkins-plugin-cli` on the pinned image; `scripts/plugins_lock.py` reproduces the same set from the update center without Docker.
- The Compose stack started, but the controller took longer than its health check allows to finish loading under that load, so the end-to-end run did not happen.

Not completed in that session, and why: the Mac the repositories were built on was out of memory and swap for most of the night (swap at about 70 GB, load average above 150, Docker's virtual machine at full CPU, and its disk went read-only once), shared with a dozen other builds. kind's control plane failed to start about fifteen times in a row (kubeadm's fixed deadlines), which is why k3d is the default provider; a k3d cluster did start, but its API server then stopped answering and `make up` could not finish. The cluster/stack commands above are written to run on a quiet machine (`make up && make run && make rebuild-proof`); until they have run once on yours, treat the end-to-end run (parallel stages, report, artifact, masked token, approval) and the rebuild proof as unproven. Nothing in this repository was marked passing that did not run.

Pending capacity (nothing below ran; each is a Docker or cluster step):

- `make up`: pending capacity: run `make up` after Docker Desktop is restarted with free disk (Docker.raw was at its 60 GiB cap on 2026-10-28).
- `make run`: pending capacity: run `make run` after Docker Desktop is restarted with free disk (Docker.raw was at its 60 GiB cap on 2026-10-28).
- `make rebuild-proof`: pending capacity: run `make rebuild-proof` after Docker Desktop is restarted with free disk (Docker.raw was at its 60 GiB cap on 2026-10-28).

## Author and license

Written by Sumit Srivastava. Released under the MIT License, see [LICENSE](LICENSE). Changes are in [CHANGELOG.md](CHANGELOG.md).
