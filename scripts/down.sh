#!/usr/bin/env bash
# Stops the stack and deletes its volumes (the controller's home, the agent's workspace and Maven cache, the Git repositories).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require docker

cd "${ROOT}"
docker compose down --volumes --remove-orphans
