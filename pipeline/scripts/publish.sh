#!/usr/bin/env bash
# Uploads one file to the artifact store with a bearer token.
#   TOKEN=... pipeline/scripts/publish.sh <file>
# Environment: TOKEN (required), PUBLISH_URL (default http://publish-sink:8080).
# The token travels in a header read from standard input, so it never appears in a process list or a trace.
set -euo pipefail
set +x

file="${1:?usage: publish.sh <file>}"
: "${TOKEN:?TOKEN must be set (bind the publish-token credential around this step)}"
url="${PUBLISH_URL:-http://publish-sink:8080}"
name="$(basename "${file}")"
[ -f "${file}" ] || { echo "publish: no such file: ${file}" >&2; exit 2; }

echo "publish: uploading ${name} ($(wc -c < "${file}" | tr -d ' ') bytes) to ${url}"
response="$(printf 'Authorization: Bearer %s\n' "${TOKEN}" |
  curl --silent --show-error --fail-with-body --max-time 60 \
    --retry 3 --retry-delay 2 --retry-connrefused --retry-all-errors \
    --header @- --upload-file "${file}" "${url}/artifacts/${name}")" || {
  echo "publish: the store refused the upload" >&2
  exit 1
}
echo "publish: stored ${response}"
