# 0002. The agent reads its own connection secret from the controller

## Context

An inbound agent needs a secret that Jenkins derives from the node name and the controller's own key. It is different for every controller home, so it cannot be written down in Git or compose.

## Decision

The agent image's entrypoint authenticates to the controller with the admin credentials from its environment, reads `/computer/<name>/jenkins-agent.jnlp`, takes the 64-character secret, unsets the admin password and starts the standard agent over a WebSocket.

## Alternatives

- **Copy the secret by hand into `.env`.** A manual step that breaks "start it again and it comes back".
- **A cloud template (Kubernetes or Docker plugin).** The right answer at scale (the third Jenkins project) and a plugin plus a socket mount for one fixed agent.

## Consequences

- The agent's container holds the admin password only until the entrypoint has read the secret. A production setup would use a dedicated, narrowly scoped user or token for this call.
