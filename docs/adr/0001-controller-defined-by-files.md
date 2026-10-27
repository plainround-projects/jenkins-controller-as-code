# 0001. The controller is defined by files, and nothing else

## Context

A Jenkins controller configured by clicking is a pet: its state is in a volume nobody can review. The lesson asks for a controller that can be destroyed and recreated identical.

## Decision

Four files define it: the `Dockerfile` (a pinned image, no setup wizard), `controller/plugins.lock.txt` (every plugin at an exact version), `controller/casc/jenkins.yaml` (configuration as code) and the environment (`.env`) for the three values that are secret. The casc file is copied outside `JENKINS_HOME`, so a volume cannot hide it. The job itself is created by the casc file (Job DSL), so even "which pipelines exist" is code.

## Alternatives

- **Plugins installed from the UI.** They live in the volume and drift from the image.
- **Only `plugins.txt` with top-level plugins.** `jenkins-plugin-cli` resolves dependencies to the newest compatible versions on the day, so two builds a week apart can differ. The lock file names all of them; `make plugins-lock` regenerates it and the diff is reviewed.

## Consequences

- `make rebuild-proof` can delete the container and its volume and compare the exported configuration before and after.
- What is not reproduced: build history, console logs, and the secret values themselves (only ids and types are in Git).
