# Apache Maven

## 1. What it is

Maven is a build tool for Java. A file called `pom.xml` (Project Object Model) says what the project is, which libraries it needs and which **plugins** run at which step. Maven's **lifecycle** is a fixed sequence of phases (`compile`, `test`, `package`, `verify`, ...); a plugin **goal** (such as `surefire:test`) does one job. The **wrapper** (`mvnw`) downloads and runs a pinned Maven so nobody installs it.

## 2. Why this repository uses it

The pipeline calls Maven goals one by one (`checkstyle:check`, `package`, `surefire:test`, `failsafe:integration-test`, `jacoco:check`) so each stage reports separately. Versions of Maven and every plugin are pinned.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `app/pom.xml` | dependencies, plugins and their configuration |
| `app/mvnw, mvnw.cmd, .mvn/wrapper/maven-wrapper.properties` | the wrapper: Maven 3.9.16 |
| `Jenkinsfile` | calls `./mvnw --batch-mode --no-transfer-progress <goals>` |
| `Makefile (`lint-app`, `test`)` | `checkstyle:check` and `verify` |
| `docker-compose.yml (`maven_cache` volume)` | keeps downloaded libraries between builds |

## 4. How it works underneath

- **Coordinates**: `groupId:artifactId:version` identify a library or plugin (`dev.plainround:order-summary:1.0.0`). Maven downloads them from Maven Central into `~/.m2`.
- `<dependencies>` lists libraries with a `<scope>` (`test` means only for tests).
- Lifecycle phases run in order; asking for a phase runs all before it. Calling a **goal directly** (`mvn surefire:test`) runs just that goal.
- **Surefire** runs unit tests; **Failsafe** runs integration tests in `integration-test` and checks the result in `verify` (so cleanup can run in between).
- A goal can have several **executions** with ids and their own configuration; `jacoco:prepare-agent@agent` runs the execution whose id is `agent`.
- `<properties>` hold variables used as `${name}`.
- The **wrapper** reads `maven-wrapper.properties` for the Maven download URL; `distributionType=only-script` means the wrapper is just a script (no extra jar).

## 5. Walkthrough of this repository's use

```xml
<properties>
  <maven.compiler.release>21</maven.compiler.release>
  <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  <project.build.outputTimestamp>2026-10-27T00:00:00Z</project.build.outputTimestamp>
  <junit.version>6.1.3</junit.version>
  <archunit.version>1.5.1</archunit.version>
  <assertj.version>3.27.7</assertj.version>
  <surefireArgLine></surefireArgLine>
</properties>
```
Compile for Java 21; read sources as UTF-8; a fixed **output timestamp** makes the jar identical on every build (reproducible builds); versions of the three test libraries; an empty `surefireArgLine` that JaCoCo fills (see below), empty by default so Surefire also runs without JaCoCo.

```xml
<build>
  <finalName>order-summary-${project.version}</finalName>
```
The jar is `order-summary-1.0.0.jar` (the Jenkinsfile's `JAR`).

`maven-compiler-plugin 3.16.0`: `<showWarnings>true</showWarnings>` and `<compilerArgs>-Xlint:all</compilerArgs><arg>-Werror</arg>`: all warnings on, warnings are errors.

`maven-jar-plugin 3.5.1`: `<mainClass>dev.plainround.orders.interfaces.Main</mainClass>` is written to the jar's manifest, so `java -jar order-summary-1.0.0.jar orders.csv` works.

`maven-surefire-plugin 3.6.1`: `<argLine>@{surefireArgLine}</argLine>` adds the JVM argument that attaches JaCoCo (the `@{...}` form is read late, after JaCoCo has set it); `<excludes>**/*IT.java</excludes>` keeps integration tests out of the unit run.

`maven-failsafe-plugin 3.6.1`: executions bind the goals `integration-test` and `verify`; `<includes>**/*IT.java</includes>` selects the integration tests.

`jacoco-maven-plugin 0.8.16` has three executions:
* id `agent`, goal `prepare-agent`, `destFile` = `target/jacoco-unit.exec`, `propertyName` = `surefireArgLine`: sets up the coverage agent only for the unit tests.
* id `coverage`, goal `check`, phase `verify`: reads the data file and applies a rule: for the **packages** `...domain` and `...application`, the `LINE` counter's `COVEREDRATIO` must be at least `0.95`.
* id `report`, goal `report`, phase `verify`: writes the HTML report.

`maven-checkstyle-plugin 3.6.0` with Checkstyle 14.3.0: `configLocation` is `config/checkstyle/checkstyle.xml`, test sources included, `violationSeverity` = `warning` (warnings fail the build), output on the console.

`<pluginManagement>` pins the versions of the clean, resources and install plugins that the lifecycle uses implicitly, so no plugin version comes from Maven's defaults.

`maven-wrapper.properties`:
```
wrapperVersion=3.3.4
distributionType=only-script
distributionUrl=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.16/apache-maven-3.9.16-bin.zip
```
The wrapper downloads Maven 3.9.16 on first use.

The pipeline's flags: `--batch-mode` (no colors or prompts), `--no-transfer-progress` (no download progress lines in the log).

## 6. Try it yourself

1. `cd app && ./mvnw --batch-mode --no-transfer-progress -v` : Maven 3.9.16 and Java 21.
2. `./mvnw --batch-mode --no-transfer-progress verify` : compile, unit tests, package, integration tests, coverage check (33 unit tests, 9 integration tests).
3. `./mvnw --batch-mode --no-transfer-progress jacoco:prepare-agent@agent surefire:test` then `ls target/jacoco-unit.exec` : the data file exists.
4. `./mvnw --batch-mode --no-transfer-progress dependency:tree` (downloads a plugin on first use) : the test libraries.
5. `BREAK_A_TEST=true ./mvnw --batch-mode surefire:test` : one test fails: `PipelineSwitchTest`.

## 7. Mistakes people make

- Calling `mvn` from a machine with a different version. The wrapper makes the version a project fact.
- Unpinned plugin versions: Maven picks defaults that change between releases.
- Reading JaCoCo's `check` as proof of coverage when the data file is missing: JaCoCo skips quietly. The Jenkinsfile requires the file first.
- Running integration tests under the same coverage agent in parallel: they would share a data file. Only unit tests run under it.

## 8. Check yourself

1. What does `pom.xml` describe?
   *Answer:* The project, its dependencies and the plugins that build it.
2. What is the difference between Surefire and Failsafe?
   *Answer:* Surefire runs unit tests; Failsafe runs integration tests and verifies them in a later phase.
3. What does `jacoco:prepare-agent@agent` mean?
   *Answer:* Run the `prepare-agent` goal's execution with id `agent`.
4. Why a fixed `outputTimestamp`?
   *Answer:* So the jar is identical on every build.
5. What does the wrapper do?
   *Answer:* Downloads and runs the pinned Maven version.

## 9. Further reading

- Maven: <https://maven.apache.org/guides/> (3.9.16). Surefire/Failsafe 3.6.1: <https://maven.apache.org/surefire/>. JaCoCo Maven plugin 0.8.16: <https://www.jacoco.org/jacoco/trunk/doc/maven.html>. Not re-checked against each exact plugin page in this session.
