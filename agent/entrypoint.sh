#!/bin/sh
# Waits for the controller, reads this agent's connection secret from its API (authenticating with the admin
# credentials from the environment), forgets the credentials, and starts the agent.
set -eu

: "${JENKINS_URL:?set JENKINS_URL}"
: "${JENKINS_AGENT_NAME:?set JENKINS_AGENT_NAME}"
: "${ADMIN_USER:=admin}"
: "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}"

secret=""
while [ -z "${secret}" ]; do
  secret="$(curl -fsS -u "${ADMIN_USER}:${ADMIN_PASSWORD}" "${JENKINS_URL}/computer/${JENKINS_AGENT_NAME}/jenkins-agent.jnlp" 2>/dev/null |
    sed -n 's:.*<argument>\([0-9a-f]\{64\}\)</argument>.*:\1:p' | head -n 1 || true)"
  [ -n "${secret}" ] || { echo "waiting for the controller to offer a secret for ${JENKINS_AGENT_NAME}"; sleep 3; }
done

unset ADMIN_PASSWORD
export JENKINS_SECRET="${secret}" JENKINS_WEB_SOCKET=true
exec /usr/local/bin/jenkins-agent
