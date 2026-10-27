# 0004. The approval is a stage with no agent

## Context

A manual approval can wait for hours. A pipeline with a top-level agent holds an executor for all of them.

## Decision

The pipeline has `agent none`. The verify and publish stages declare their own agent; the approval stage declares none, so while it waits no executor is held. The jar travels between the two agent allocations with `stash` and `unstash`.

## Consequences

- The end-to-end test starts a build with `REQUIRE_APPROVAL=true`, waits for the pending input and asserts that the agent has no running executable while it waits, then approves through the API.
- `input` is restricted to the `admin` submitter; real teams would name a group.
