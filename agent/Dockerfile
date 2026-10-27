# The build agent: the official inbound agent (JDK 21 and git) with an entrypoint that asks the controller for this
# agent's secret, so the secret is never in the repository or the compose file.
ARG AGENT_IMAGE=jenkins/inbound-agent:3391.va_37fa_a_305d6d-8-jdk21@sha256:cd373fdeb8d9388e7deca4195b9fa9b5dd28ba70c9d9ba2b90ba67346f4ab8f8
FROM ${AGENT_IMAGE}

COPY --chmod=0755 entrypoint.sh /usr/local/bin/agent-entrypoint.sh

USER jenkins
ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
