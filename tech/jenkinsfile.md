# Jenkins Pipeline (the Jenkinsfile)

## 1. What it is

A **Jenkinsfile** is a text file in the code repository that describes a build as a pipeline of **stages**. This repository uses the **declarative** syntax: a fixed structure (`pipeline { agent ...; stages { stage(...) { steps { ... } } } }`) written in a Groovy-based format that Jenkins validates before running.

## 2. Why this repository uses it

The pipeline is code in Git next to the code it builds. It runs lint, build, unit and integration tests in parallel, a coverage rule, an optional manual approval that does not hold an executor, and a publish step with a credential visible only inside one block.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `Jenkinsfile` | the pipeline |
| `controller/casc/jenkins.yaml` | the job that reads it |
| `pipeline/scripts/` | the shell scripts the stages call |
| `scripts/lint-jenkinsfile.sh` | validation by the controller |
| `tests/unit/` | structure tests of the Jenkinsfile (stages, parameters, agent none) |
| `tests/stack/test_pipeline.py` | runs it for real |

## 4. How it works underneath

- `agent none` at the top means no stage gets an agent unless it asks for one; each stage then sets its own `agent { label '...' }`. A stage with no agent (like `Approve`) holds **no executor** while it waits.
- `parameters { booleanParam(...) }` defines inputs shown on "Build with Parameters"; read them as `params.NAME`.
- `options { timeout(...); timestamps(); buildDiscarder(...); disableConcurrentBuilds() }` set job-wide behavior.
- `environment { ... }` defines variables available to every stage.
- Nested `stages` run in order; `parallel { stage(...) { ... } stage(...) { ... } }` runs branches at the same time; `failFast true` stops the others when one fails.
- `post { always { ... } success { ... } }` runs after a stage depending on its result.
- `stash` saves files from one agent workspace and `unstash` restores them in another stage (possibly on a different agent).
- `input` pauses the build until a person approves; `submitter` limits who may.
- Steps run on the **controller's JVM as Groovy** but each `sh` step runs a shell command on the agent.

## 5. Walkthrough of this repository's use

```groovy
pipeline {
    agent none
    parameters {
        booleanParam(name: 'REQUIRE_APPROVAL', defaultValue: false, description: 'Hold the publish step until a person approves it')
        booleanParam(name: 'ECHO_TOKEN', defaultValue: false, description: '...')
        booleanParam(name: 'BREAK_A_TEST', defaultValue: false, description: '...')
    }
    options {
        timeout(time: 20, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }
    environment {
        MVN = './mvnw --batch-mode --no-transfer-progress'
        JAR = 'order-summary-1.0.0.jar'
    }
```
Three switches that make the lesson's behaviors demonstrable. The whole run times out after 20 minutes; every log line has a time stamp; only the last 20 builds are kept; two builds of the job never run at once. `MVN` is a shell fragment reused in the stages (`sh "${MVN} checkstyle:check"`: Groovy replaces `${MVN}` before the shell sees the command).

```groovy
        stage('Verify') {
            agent { label 'docker-agent' }
            stages {
                stage('Lint')  { steps { dir('app') { sh "${MVN} checkstyle:check" } } }
                stage('Build') { steps { dir('app') { sh "${MVN} -DskipTests package" } } }
```
`Verify` has an agent; it contains nested stages that share one workspace. `dir('app')` changes into the Maven project; `sh` runs a command on the agent.

```groovy
                stage('Test') {
                    failFast true
                    parallel {
                        stage('Unit') {
                            steps { dir('app') { withEnv(["BREAK_A_TEST=${params.BREAK_A_TEST}"]) { sh "${MVN} jacoco:prepare-agent@agent surefire:test" } } }
                            post { always { junit 'app/target/surefire-reports/*.xml' } }
                        }
                        stage('Integration') {
                            steps { dir('app') { sh "${MVN} failsafe:integration-test failsafe:verify" } }
                            post { always { junit 'app/target/failsafe-reports/*.xml' } }
                        }
                    }
                }
```
Unit and integration tests run **in parallel**. `withEnv` sets `BREAK_A_TEST` for the unit run (a test fails when it is `true`). `jacoco:prepare-agent@agent` attaches the coverage agent using the `agent` execution from the POM; `surefire:test` runs the unit tests; `failsafe:integration-test failsafe:verify` runs the `*IT` classes and fails the build if any failed. `junit '...xml'` publishes the test reports, in `post { always }` so a failing run still reports.

```groovy
                stage('Coverage') {
                    steps { dir('app') { sh "test -f target/jacoco-unit.exec && ${MVN} jacoco:report@report jacoco:check@coverage" } }
                }
            }
            post {
                success { stash name: 'jar', includes: 'app/target/*.jar', excludes: 'app/target/*-sources.jar' }
                always { sh 'pipeline/scripts/test-summary.sh app/target/surefire-reports app/target/failsafe-reports || true' }
            }
        }
```
JaCoCo skips quietly when it has no data, so `test -f target/jacoco-unit.exec &&` makes the stage fail if the unit tests did not write coverage data. On success the jar is **stashed** for the later stage; always, the summary script prints test totals (`|| true`: a summary problem must not fail the build).

```groovy
        stage('Approve') {
            when { expression { params.REQUIRE_APPROVAL } }
            agent none
            options { timeout(time: 10, unit: 'MINUTES') }
            steps { input message: 'Publish order-summary?', ok: 'Publish', submitter: 'admin' }
        }
```
Runs only when the parameter is true. `agent none` means it holds no executor while a person decides. Ten minutes at most; only `admin` may approve.

```groovy
        stage('Publish') {
            agent { label 'docker-agent' }
            steps {
                unstash 'jar'
                withCredentials([string(credentialsId: 'publish-token', variable: 'TOKEN')]) {
                    script { if (params.ECHO_TOKEN) { sh 'echo "token=$TOKEN"' } }
                    sh 'pipeline/scripts/publish.sh "app/target/${JAR}"'
                }
            }
            post { success { archiveArtifacts artifacts: 'app/target/*.jar', fingerprint: true } }
        }
```
`unstash` restores the jar. `withCredentials` binds the stored `publish-token` to the environment variable `TOKEN` **only inside the block**. Note the single quotes in `sh '...$TOKEN...'`: the shell, not Groovy, expands the variable, which is the safe form (Groovy would put the secret in the command string). `script { }` allows ordinary Groovy `if` inside declarative syntax. With `ECHO_TOKEN` true, the build log still shows `token=****`: Jenkins **masks** the value. `archiveArtifacts ... fingerprint: true` keeps the jar with the build and records its checksum.







<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every line of the `Jenkinsfile`

A `Jenkinsfile` is a text file kept in the project's Git repository that tells Jenkins what to do when a build runs: which machine to use, which commands to run, in which order. This one uses the **declarative** syntax: a fixed structure of named blocks (`pipeline`, `stages`, `stage`, `steps`), written in Groovy-like syntax, instead of free-form programming. The language is Groovy, but in declarative style you only need to know the blocks and the **steps** (ready-made commands such as `sh`, which runs a shell command).

```groovy
// Declarative pipeline for order-summary. The controller that runs it is defined by controller/casc/jenkins.yaml.
//   Verify (agent): Lint, Build, Test (unit and integration in parallel), Coverage
//   Approve (no agent): an optional manual approval that holds no executor while it waits
//   Publish (agent): uploads the jar with a token bound to that one step
pipeline {
    agent none
```
- Lines 1-4 are comments (`//` starts a comment in Groovy). They summarise the stages.
- Line 5 opens the `pipeline { ... }` block. Everything must live inside it.
- Line 6, `agent none`, means "do not reserve a machine for the whole pipeline". Each stage asks for its own agent below. This matters for the approval stage: a person can take an hour to click a button, and a reserved machine would be held idle all that time.

```groovy
    parameters {
        booleanParam(name: 'REQUIRE_APPROVAL', defaultValue: false, description: 'Hold the publish step until a person approves it')
        booleanParam(name: 'ECHO_TOKEN', defaultValue: false, description: 'Make the publish step echo its token, to show that the log masks it')
        booleanParam(name: 'BREAK_A_TEST', defaultValue: false, description: 'Make one unit test fail, to show how a failing test is reported')
    }
```
`parameters` declares inputs that appear as form fields on "Build with Parameters". `booleanParam` is a tick-box with a `name`, a `defaultValue` and a `description`. Inside the pipeline their values are read as `params.NAME`. All three are `false` by default; they exist so the demonstration run can switch on an approval step, a token echo, and a deliberately failing test.

```groovy
    options {
        timeout(time: 20, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }
```
`options` holds pipeline-wide settings. `timeout` aborts the build after 20 minutes. `timestamps()` prefixes every log line with the time. `buildDiscarder(logRotator(numToKeepStr: '20'))` keeps only the last 20 builds' records so the disk does not fill. `disableConcurrentBuilds()` stops two builds of this job from running at once.

```groovy
    environment {
        MVN = './mvnw --batch-mode --no-transfer-progress'
        JAR = 'order-summary-1.0.0.jar'
    }
```
`environment` defines environment variables for every `sh` step. `MVN` is the Maven command line with two flags (`--batch-mode` for no interactive output, `--no-transfer-progress` to hide download bars), reused with `${MVN}`. `JAR` is the file name of the artifact the Publish stage uploads.

```groovy
    stages {
        stage('Verify') {
            agent { label 'docker-agent' }
            stages {
```
`stages` lists the stages in order. `stage('Verify')` has its own `agent { label 'docker-agent' }`: run this stage on a node that has the label `docker-agent` (the container agent defined in the configuration file). A stage can itself hold `stages`, which makes Verify a group of sub-stages sharing one workspace.

```groovy
                stage('Lint') {
                    steps { dir('app') { sh "${MVN} checkstyle:check" } }
                }
                stage('Build') {
                    steps { dir('app') { sh "${MVN} -DskipTests package" } }
                }
```
- `Lint`: `dir('app') { ... }` changes into the `app` folder for the commands inside. `sh "${MVN} checkstyle:check"` runs the shell command; the double-quoted string lets Groovy insert `${MVN}`. Checkstyle checks the Java source against the style rules.
- `Build`: `package -DskipTests` compiles and packs the jar, skipping tests (they run in the next stage).

```groovy
                stage('Test') {
                    failFast true
                    parallel {
                        stage('Unit') {
                            steps {
                                dir('app') {
                                    withEnv(["BREAK_A_TEST=${params.BREAK_A_TEST}"]) { sh "${MVN} jacoco:prepare-agent@agent surefire:test" }
                                }
                            }
                            post { always { junit 'app/target/surefire-reports/*.xml' } }
                        }
                        stage('Integration') {
                            steps { dir('app') { sh "${MVN} failsafe:integration-test failsafe:verify" } }
                            post { always { junit 'app/target/failsafe-reports/*.xml' } }
                        }
                    }
                }
```
`Test` contains `parallel { ... }`, whose stages run at the same time on the same agent (it has two executors). `failFast true` aborts the sibling as soon as one fails.

- `Unit`: `withEnv([...])` sets an environment variable for the steps inside; here `BREAK_A_TEST` is passed from the parameter. The Maven command runs the `jacoco:prepare-agent@agent` goal (it attaches the coverage recorder to the test JVM) and then `surefire:test` (run the unit tests). `post { always { junit '...' } }` runs after the stage whatever the result and tells Jenkins to read the XML test reports in that folder, so the results page shows each test.
- `Integration`: `failsafe:integration-test failsafe:verify` runs the slower tests (files ending `IT`) and then fails the build if any of them failed. The two goals are separate because Failsafe delays the failure until after cleanup.

```groovy
                stage('Coverage') {
                    steps {
                        dir('app') {
                            // jacoco skips quietly when it has no data, so require the unit tests' data file first.
                            sh "test -f target/jacoco-unit.exec && ${MVN} jacoco:report@report jacoco:check@coverage"
                        }
                    }
                }
            }
```
`Coverage` produces the coverage report and enforces the minimum. The comment above the `sh` line explains the guard: JaCoCo (the coverage tool) skips quietly when it has no data file, so `test -f target/jacoco-unit.exec &&` first demands that the unit-test data file exists. `&&` runs the next command only if the previous one succeeded. `jacoco:report@report jacoco:check@coverage` names two executions defined in the `pom.xml`: one builds the report, one fails below the threshold. Lines 60-61 close the nested `stages` of Verify.

```groovy
            post {
                success { stash name: 'jar', includes: 'app/target/*.jar', excludes: 'app/target/*-sources.jar' }
                always { sh 'pipeline/scripts/test-summary.sh app/target/surefire-reports app/target/failsafe-reports || true' }
            }
        }
```
The `post` block of the Verify stage. `success` runs only when the stage passed; it calls `stash`, which copies the named files from the agent into the controller's storage under the name `jar` so another stage (maybe on another machine) can `unstash` them. `excludes` leaves out the sources jar. `always` runs the summary script even when tests failed; `|| true` forces a successful exit code so a problem in the summary script cannot hide the real result.

```groovy
        stage('Approve') {
            when { expression { params.REQUIRE_APPROVAL } }
            agent none
            options { timeout(time: 10, unit: 'MINUTES') }
            steps { input message: 'Publish order-summary?', ok: 'Publish', submitter: 'admin' }
        }
```
`Approve` is the optional manual gate. `when { expression { params.REQUIRE_APPROVAL } }` makes the stage run only when the tick-box was set (an `expression` is any Groovy true/false). It has `agent none`, so it uses no executor while waiting. `options { timeout ... }` limits the wait to 10 minutes. `input` pauses the build and shows a button: `message` is the question, `ok` the button label, and `submitter: 'admin'` restricts who may click it.

```groovy
        stage('Publish') {
            agent { label 'docker-agent' }
            steps {
                unstash 'jar'
                // The token exists only inside this block, and only for the steps written here.
                withCredentials([string(credentialsId: 'publish-token', variable: 'TOKEN')]) {
                    script {
                        if (params.ECHO_TOKEN) {
                            sh 'echo "token=$TOKEN"'
                        }
                    }
                    sh 'pipeline/scripts/publish.sh "app/target/${JAR}"'
                }
            }
```
`Publish` runs on the agent again. `unstash 'jar'` brings back the jar saved by Verify. `withCredentials([string(credentialsId: 'publish-token', variable: 'TOKEN')])` fetches the secret text stored under the id `publish-token` and exposes it as `$TOKEN` only inside the braces; Jenkins also replaces its value with `****` in the log. The `script { ... }` block lets this declarative pipeline use ordinary Groovy `if`. When the `ECHO_TOKEN` parameter is on, the single-quoted `sh 'echo "token=$TOKEN"'` is executed by the shell (not Groovy), which demonstrates the masking. Line 86 runs the publish script with the jar path; `${JAR}` there is expanded by the shell from the environment block.

```groovy
            post {
                success { archiveArtifacts artifacts: 'app/target/*.jar', fingerprint: true }
            }
        }
    }
}
```
On success, `archiveArtifacts` stores the jar with the build record in Jenkins and `fingerprint: true` records its checksum so Jenkins can track where the file is used. The last lines close `stages` and `pipeline`.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `make lint-jenkinsfile` : `Jenkinsfile successfully validated.`
2. In the UI choose *Build with Parameters*, set `BREAK_A_TEST` true : the build fails in the Unit stage; the test report shows the one failing test.
3. Set `REQUIRE_APPROVAL` true : the build waits at *Approve* with no executor held (check *Manage Jenkins > Nodes*).
4. Set `ECHO_TOKEN` true : the log shows `token=****`.
5. `.venv/bin/pytest tests/unit/test_jenkinsfile.py -q` : structure tests of the file.

## 7. Mistakes people make

- Interpolating a secret in a double-quoted `sh "..."` string: Groovy puts it in the command, where it can leak. Use single quotes so the shell reads the variable.
- Holding an executor for an approval (`agent` at the top). `agent none` and a per-stage agent avoid it.
- Putting logic in Groovy that belongs in a script you can test (`pipeline/scripts/*.sh` are tested offline).
- Forgetting `post { always { junit ... } }`: a failing test then has no report.

## 8. Check yourself

1. What does `agent none` at the top mean?
   *Answer:* No stage has an agent unless it declares one.
2. Why does the `Approve` stage have `agent none`?
   *Answer:* So waiting for a person holds no executor.
3. What does `stash` do?
   *Answer:* Saves files so a later stage (maybe on another agent) can `unstash` them.
4. Why single quotes in `sh 'echo $TOKEN'`?
   *Answer:* The shell expands the variable; Groovy never sees the secret.
5. What does `failFast true` do in `parallel`?
   *Answer:* Stops the other branches when one fails.

## 9. Further reading

- Pipeline syntax: <https://www.jenkins.io/doc/book/pipeline/syntax/> and the Pipeline Steps reference <https://www.jenkins.io/doc/pipeline/steps/>. Not re-checked against the exact plugin versions in the lock in this session.
