#!/usr/bin/env bash
# Asks the running controller to validate the Jenkinsfile with its own declarative linter.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require curl

jar="$(mktemp)"
trap 'rm -f "${jar}"' EXIT
auth=(-u "admin:${ADMIN_PASSWORD:?run make up first}" -b "${jar}" -c "${jar}")
crumb="$(curl -fsS "${auth[@]}" "${CONTROLLER_URL}/crumbIssuer/api/json" | sed -E 's/.*"crumbRequestField":"([^"]+)".*"crumb":"([^"]+)".*/\1:\2/')"
result="$(curl -fsS "${auth[@]}" -H "${crumb}" -X POST --data-urlencode "jenkinsfile@${ROOT}/Jenkinsfile" \
  "${CONTROLLER_URL}/pipeline-model-converter/validate")"
echo "${result}"
grep -q 'successfully validated' <<<"${result}"
