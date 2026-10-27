#!/usr/bin/env bash
# Pushes a snapshot of this repository (tracked files and new files that are not ignored) to the Git server inside
# the compose project, as the repository the Jenkins job builds. Run it after any change you want Jenkins to see.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require git tar curl

snapshot="$(mktemp -d)"
trap 'rm -rf "${snapshot}"' EXIT
(cd "${ROOT}" && git ls-files --cached --others --exclude-standard -z | xargs -0 tar -cf -) | tar -xf - -C "${snapshot}"

git -C "${snapshot}" init --quiet --initial-branch=main
git -C "${snapshot}" config user.name "Seed"
git -C "${snapshot}" config user.email "seed@example.invalid"
git -C "${snapshot}" config commit.gpgsign false
git -C "${snapshot}" add --all
git -C "${snapshot}" commit --quiet -m "Snapshot of controller-as-code"
wait_for "the Git server" 60 curl -fsS "http://127.0.0.1:${GIT_PORT}/controller-as-code.git/info/refs?service=git-upload-pack"
git -C "${snapshot}" push --quiet --force "http://127.0.0.1:${GIT_PORT}/controller-as-code.git" main
log "seeded controller-as-code at $(git -C "${snapshot}" rev-parse --short HEAD)"
