#!/usr/bin/env bash
# Everything `make up` does: secrets, images, containers, and the repository the job builds.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require docker curl git

"${ROOT}/scripts/init-env.sh"
# .env exists now; read it (lib.sh loaded before the file existed).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "${ROOT}"
docker compose up --detach --build --wait --wait-timeout 600
"${ROOT}/scripts/seed-project.sh"
wait_for "the agent to be online" 180 bash -c "curl -fsS -u admin:\"\${ADMIN_PASSWORD}\" ${CONTROLLER_URL}/computer/docker-agent/api/json | grep -q '\"offline\":false'"
log "controller: ${CONTROLLER_URL}  (user admin, password in .env)"
