# 0003. Maven with the wrapper for the project the pipeline builds

## Context

The lesson's sample Jenkinsfile uses Gradle (`./gradlew assemble`). The track needs a Java project with a unit-test step and an integration-test step that can run in parallel stages.

## Decision

Maven with a checked-in wrapper. Surefire runs the `*Test` classes, Failsafe the `*IT` classes, and each writes its report to its own directory, so the two stages run side by side against the compiled classes without sharing state. Gradle would run both from one project directory and lock it.

## Consequences

- The Jenkinsfile calls plugin goals directly (`surefire:test`, `failsafe:integration-test failsafe:verify`) after one `package` run, which is what makes the parallel stages cheap.
- Any Java build tool fits the same pipeline shape; the stage names and report paths are the contract.
