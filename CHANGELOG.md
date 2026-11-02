# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- The agent's Maven cache volume is writable by the build user (found by the first live run).
- The stack tests start the parameterised job with a parameter, read the test report's `passCount`, `failCount` and `skipCount`, and approve with a form body; `scripts/lint-jenkinsfile.sh` reads the crumb fields in the right order.

## [0.1.0] - 2026-10-27

### Added

- A Jenkins controller defined only by files: a pinned image, `controller/plugins.txt` and its resolved `plugins.lock.txt`, and `controller/casc/jenkins.yaml` (security, zero executors, an inbound agent node, a credential whose secret comes from the environment, and the job).
- A container agent whose entrypoint reads its own connection secret from the controller, so no agent secret is stored.
- `docker-compose.yml` with the controller, the agent, a Git server the job builds from and an artifact store the job publishes to; credentials only from `.env`.
- The declarative `Jenkinsfile`: lint, build, parallel unit and integration tests with their own reports, coverage, an optional approval that holds no executor, and a publish step with the token bound to it alone.
- `order-summary`, the Java project the pipeline builds: layered (domain, application, infrastructure, interfaces), typed with records, tested with JUnit and ArchUnit, with checkstyle and a JaCoCo gate.
- Tests of the pipeline's scripts, the artifact store, the configuration and the Jenkinsfile, and an end-to-end run that triggers the job through the API and asserts the result.
