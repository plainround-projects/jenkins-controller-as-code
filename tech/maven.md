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




<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: `app/pom.xml`

Maven is a build tool for Java. Its input is one XML file, `pom.xml` (Project Object Model), that says what the project is, which libraries it needs and which **plugins** (programs that do one job such as compiling or testing) run during the build. XML is text built from nested tags: `<name>value</name>`; a tag can hold other tags, and an attribute such as `xmlns="..."` sits inside the opening tag. Maven's build follows a fixed **lifecycle**: a list of phases (`compile`, `test`, `package`, `verify`, ...). Running a phase runs every earlier phase first. Plugins attach *goals* to phases; you can also run a goal directly, written `plugin:goal` (for example `checkstyle:check`).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <groupId>dev.plainround</groupId>
  <artifactId>order-summary</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>
  <name>order-summary</name>
  <description>Summarizes an orders CSV per customer; the project the Jenkins pipeline builds and tests.</description>
```
Line 1 is the XML declaration (version and character encoding). The `<project>` element is the root; `xmlns` names the XML vocabulary and `xsi:schemaLocation` points editors to the schema that describes valid tags. `modelVersion` is always 4.0.0. The *coordinates* `groupId` (owner), `artifactId` (project name) and `version` identify the artifact: `dev.plainround:order-summary:1.0.0`. `packaging` `jar` means the result is a Java archive. `name` and `description` are human-readable.

```xml
  <properties>
    <maven.compiler.release>21</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <project.build.outputTimestamp>2026-10-27T00:00:00Z</project.build.outputTimestamp>
    <junit.version>6.1.3</junit.version>
    <archunit.version>1.5.1</archunit.version>
    <assertj.version>3.27.7</assertj.version>
    <!-- Filled in by jacoco:prepare-agent when it runs; empty otherwise, so surefire can also run on its own. -->
    <surefireArgLine></surefireArgLine>
  </properties>
```
`<properties>` are named values reused as `${name}`. `maven.compiler.release` 21 compiles for Java 21. `project.build.sourceEncoding` fixes the text encoding of source files. `project.build.outputTimestamp` makes the jar *reproducible*: every file inside gets this fixed time, so building twice gives byte-identical jars. The three `*.version` properties pin the test libraries. `surefireArgLine` is deliberately empty; the JaCoCo plugin fills it in when it runs (the comment says so) so the test plugin can run alone too.

```xml
  <dependencies>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>${junit.version}</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <version>${assertj.version}</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>com.tngtech.archunit</groupId>
      <artifactId>archunit-junit5</artifactId>
      <version>${archunit.version}</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
```
`<dependencies>` are libraries downloaded from a repository. `scope` `test` means they are only on the classpath when tests run and are not packaged into the jar. JUnit Jupiter is the test framework, AssertJ gives readable assertions, ArchUnit tests the code's architecture rules.

```xml
  <build>
    <finalName>order-summary-${project.version}</finalName>
    <pluginManagement>
      <plugins>
        <plugin>
          <artifactId>maven-clean-plugin</artifactId>
          <version>3.5.0</version>
        </plugin>
        <plugin>
          <artifactId>maven-resources-plugin</artifactId>
          <version>3.5.0</version>
        </plugin>
        <plugin>
          <artifactId>maven-install-plugin</artifactId>
          <version>3.1.4</version>
        </plugin>
      </plugins>
    </pluginManagement>
```
`finalName` sets the output file name `order-summary-1.0.0` (plus `.jar`). `pluginManagement` fixes the versions of three plugins Maven uses by default (clean, resources, install), so their versions do not depend on the Maven version installed.

```xml
    <plugins>
      <plugin>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.16.0</version>
        <configuration>
          <showWarnings>true</showWarnings>
          <compilerArgs>
            <arg>-Xlint:all</arg>
            <arg>-Werror</arg>
          </compilerArgs>
        </configuration>
      </plugin>
      <plugin>
        <artifactId>maven-jar-plugin</artifactId>
        <version>3.5.1</version>
        <configuration>
          <archive>
            <manifest>
              <mainClass>dev.plainround.orders.interfaces.Main</mainClass>
            </manifest>
          </archive>
        </configuration>
      </plugin>
```
The compiler plugin 3.16.0 shows warnings and passes `-Xlint:all` (every warning category on) with `-Werror` (a warning is an error), so careless code does not compile. The jar plugin writes the `Main-Class` entry in the manifest (the jar's metadata) so `java -jar` knows where to start.

```xml
      <!-- Unit tests: *Test classes. -->
      <plugin>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>3.6.1</version>
        <configuration>
          <argLine>@{surefireArgLine}</argLine>
          <excludes>
            <exclude>**/*IT.java</exclude>
          </excludes>
        </configuration>
      </plugin>
      <!-- Integration tests: *IT classes, run against real files and the packaged command line. -->
      <plugin>
        <artifactId>maven-failsafe-plugin</artifactId>
        <version>3.6.1</version>
        <executions>
          <execution>
            <goals>
              <goal>integration-test</goal>
              <goal>verify</goal>
            </goals>
          </execution>
        </executions>
        <configuration>
          <includes>
            <include>**/*IT.java</include>
          </includes>
        </configuration>
      </plugin>
```
Surefire runs the unit tests: `argLine` passes JVM options (here the JaCoCo agent, via the `@{surefireArgLine}` late-binding syntax), and `excludes` skips classes whose names end in `IT`. Failsafe runs those integration tests: its two goals `integration-test` (run them) and `verify` (fail the build if any failed) are bound by default to the matching lifecycle phases; the `includes` select only `*IT.java`. Splitting them keeps fast tests fast and lets the pipeline run both groups in parallel.

```xml
      <plugin>
        <groupId>org.jacoco</groupId>
        <artifactId>jacoco-maven-plugin</artifactId>
        <version>0.8.16</version>
        <executions>
          <execution>
            <id>agent</id>
            <goals>
              <goal>prepare-agent</goal>
            </goals>
            <configuration>
              <destFile>${project.build.directory}/jacoco-unit.exec</destFile>
              <!-- Only the unit tests run under the agent; the integration tests run in parallel and must not share its file. -->
              <propertyName>surefireArgLine</propertyName>
            </configuration>
          </execution>
          <execution>
            <id>coverage</id>
            <goals>
              <goal>check</goal>
            </goals>
            <phase>verify</phase>
            <configuration>
              <dataFile>${project.build.directory}/jacoco-unit.exec</dataFile>
              <rules>
                <rule>
                  <element>PACKAGE</element>
                  <includes>
                    <include>dev.plainround.orders.domain</include>
                    <include>dev.plainround.orders.application</include>
                  </includes>
                  <limits>
                    <limit>
                      <counter>LINE</counter>
                      <value>COVEREDRATIO</value>
                      <minimum>0.95</minimum>
                    </limit>
                  </limits>
                </rule>
              </rules>
            </configuration>
          </execution>
          <execution>
            <id>report</id>
            <goals>
              <goal>report</goal>
            </goals>
            <phase>verify</phase>
            <configuration>
              <dataFile>${project.build.directory}/jacoco-unit.exec</dataFile>
            </configuration>
          </execution>
        </executions>
      </plugin>
```
JaCoCo measures which lines the tests executed. It has three **executions** (named instances of the plugin's goals, selectable as `goal@id`): `agent` runs `prepare-agent`, which attaches the recorder to the test JVM and writes data to `jacoco-unit.exec`, naming the property `surefireArgLine` that carries the JVM option. `coverage` runs `check` in the `verify` phase with a rule: for the packages `domain` and `application`, covered lines divided by total lines (`COVEREDRATIO` of counter `LINE`) must be at least 0.95. `report` writes the HTML report. The comment explains that only unit tests run under the agent because integration tests run concurrently and must not share its file.

```xml
      <plugin>
        <artifactId>maven-checkstyle-plugin</artifactId>
        <version>3.6.0</version>
        <dependencies>
          <dependency>
            <groupId>com.puppycrawl.tools</groupId>
            <artifactId>checkstyle</artifactId>
            <version>14.3.0</version>
          </dependency>
        </dependencies>
        <configuration>
          <configLocation>config/checkstyle/checkstyle.xml</configLocation>
          <includeTestSourceDirectory>true</includeTestSourceDirectory>
          <consoleOutput>true</consoleOutput>
          <violationSeverity>warning</violationSeverity>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```
Checkstyle checks the source against `config/checkstyle/checkstyle.xml`. The plugin `<dependencies>` pins the Checkstyle engine version independently of the plugin. `includeTestSourceDirectory` also checks the tests, `consoleOutput` prints the findings, and `violationSeverity` `warning` makes warnings fail the build. The last tags close `plugins`, `build` and `project`.

#### The Maven wrapper: `mvnw`, `mvnw.cmd` and `.mvn/wrapper/maven-wrapper.properties`

**Why it exists.** Maven itself is a program you would normally have to install, and different installed versions behave differently. The **wrapper** is a pair of small scripts committed with the project: when you run `./mvnw`, the script reads the exact Maven version from a properties file, downloads that version once into `~/.m2/wrapper/dists`, and then runs it. Anyone (and the CI machine) gets the same Maven without installing anything. The files are generated by the Apache Maven Wrapper project (version 3.3.4); they are not hand-written, but they run in your build, so each line is explained here.

```properties
wrapperVersion=3.3.4
distributionType=only-script
distributionUrl=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.16/apache-maven-3.9.16-bin.zip
```
A `.properties` file is plain `key=value` lines. `wrapperVersion` is the wrapper's own version. `distributionType=only-script` means "do not put a wrapper jar in the repository; the scripts do the download themselves". `distributionUrl` is exactly which Maven archive to fetch: Apache Maven 3.9.16, binary zip, from Maven Central.

##### `mvnw`: the script for Linux and macOS

```bash
#!/bin/sh
# ----------------------------------------------------------------------------
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Apache Maven Wrapper startup batch script, version 3.3.4
#
# Optional ENV vars
# -----------------
#   JAVA_HOME - location of a JDK home dir, required when download maven via java source
#   MVNW_REPOURL - repo url base for downloading maven distribution
#   MVNW_USERNAME/MVNW_PASSWORD - user and password for downloading maven
#   MVNW_VERBOSE - true: enable verbose log; debug: trace the mvnw script; others: silence the output
# ----------------------------------------------------------------------------

```
Line 1, `#!/bin/sh`, makes it a plain `sh` script. Lines 2-19 are the Apache license text (comments). Lines 21-30 describe the optional environment variables: `JAVA_HOME` (a JDK folder, needed only if Maven is downloaded through Java), `MVNW_REPOURL` (a mirror to download from instead of Maven Central), `MVNW_USERNAME` and `MVNW_PASSWORD` (credentials for that mirror), and `MVNW_VERBOSE` (`true` prints progress, `debug` also traces every command).

```bash
set -euf
[ "${MVNW_VERBOSE-}" != debug ] || set -x

# OS specific support.
native_path() { printf %s\\n "$1"; }
case "$(uname)" in
CYGWIN* | MINGW*)
  [ -z "${JAVA_HOME-}" ] || JAVA_HOME="$(cygpath --unix "$JAVA_HOME")"
  native_path() { cygpath --path --windows "$1"; }
  ;;
esac
```
`set -euf` turns on three shell safety rules: `-e` stops on the first failing command, `-u` makes using an unset variable an error, `-f` disables file-name wildcard expansion (so a `*` in a variable is not expanded by accident). `"${MVNW_VERBOSE-}"` means "the variable's value, or empty if unset" (the `-` form avoids the `-u` error). The `||` runs `set -x` (print every command) only when the value is `debug`. Lines 35-42 define `native_path`, a function that prints its argument unchanged, and, on Windows-like shells (Cygwin or MinGW, detected with `uname`), redefine it to convert paths to Windows format with `cygpath`. A `case ... esac` block chooses among patterns, each ending with `;;`.

```bash
# set JAVACMD and JAVACCMD
set_java_home() {
  # For Cygwin and MinGW, ensure paths are in Unix format before anything is touched
  if [ -n "${JAVA_HOME-}" ]; then
    if [ -x "$JAVA_HOME/jre/sh/java" ]; then
      # IBM's JDK on AIX uses strange locations for the executables
      JAVACMD="$JAVA_HOME/jre/sh/java"
      JAVACCMD="$JAVA_HOME/jre/sh/javac"
    else
      JAVACMD="$JAVA_HOME/bin/java"
      JAVACCMD="$JAVA_HOME/bin/javac"

      if [ ! -x "$JAVACMD" ] || [ ! -x "$JAVACCMD" ]; then
        echo "The JAVA_HOME environment variable is not defined correctly, so mvnw cannot run." >&2
        echo "JAVA_HOME is set to \"$JAVA_HOME\", but \"\$JAVA_HOME/bin/java\" or \"\$JAVA_HOME/bin/javac\" does not exist." >&2
        return 1
      fi
    fi
  else
    JAVACMD="$(
      'set' +e
      'unset' -f command 2>/dev/null
      'command' -v java
    )" || :
    JAVACCMD="$(
      'set' +e
      'unset' -f command 2>/dev/null
      'command' -v javac
    )" || :

    if [ ! -x "${JAVACMD-}" ] || [ ! -x "${JAVACCMD-}" ]; then
      echo "The java/javac command does not exist in PATH nor is JAVA_HOME set, so mvnw cannot run." >&2
      return 1
    fi
  fi
}
```
`set_java_home` finds the Java compiler and runtime, used only when neither `wget` nor `curl` exists and Java must download the file. If `JAVA_HOME` is set it uses `$JAVA_HOME/bin/java` and `javac` (an IBM-JDK-on-AIX location is special-cased) and prints an error and returns 1 if they are not executable (`[ ! -x FILE ]` tests "not executable"). Otherwise it looks the commands up on `PATH` with `command -v`. The odd quoted forms `'set' +e` and `'unset' -f command` are deliberate: quoting the word prevents any user alias or function with that name from being used; `|| :` ignores a failure (`:` is the do-nothing command).

```bash
# hash string like Java String::hashCode
hash_string() {
  str="${1:-}" h=0
  while [ -n "$str" ]; do
    char="${str%"${str#?}"}"
    h=$(((h * 31 + $(LC_CTYPE=C printf %d "'$char")) % 4294967296))
    str="${str#?}"
  done
  printf %x\\n $h
}
```
`hash_string` reproduces Java's `String.hashCode()` in shell arithmetic, so the folder name for a given download URL is the same as other Maven tools compute. It loops over the string one character at a time (`${str%"${str#?}"}` is the first character, `${str#?}` the rest), converts the character to its numeric code with `printf %d "'c"`, multiplies the running hash by 31, adds the code, and keeps it within 32 bits with `% 4294967296`. It prints the result in hexadecimal.

```bash
verbose() { :; }
[ "${MVNW_VERBOSE-}" != true ] || verbose() { printf %s\\n "${1-}"; }

die() {
  printf %s\\n "$1" >&2
  exit 1
}
```
`verbose` is a function that does nothing by default (`:`), and is redefined to print its argument when `MVNW_VERBOSE` is `true`. `die` prints a message to standard error and exits with code 1.

```bash
trim() {
  # MWRAPPER-139:
  #   Trims trailing and leading whitespace, carriage returns, tabs, and linefeeds.
  #   Needed for removing poorly interpreted newline sequences when running in more
  #   exotic environments such as mingw bash on Windows.
  printf "%s" "${1}" | tr -d '[:space:]'
}

scriptDir="$(dirname "$0")"
scriptName="$(basename "$0")"
```
`trim` removes all whitespace (including carriage returns that sneak in on Windows) with `tr -d '[:space:]'`. `scriptDir` and `scriptName` are the folder and file name of this script (`$0` is the command as typed).

```bash
# parse distributionUrl and optional distributionSha256Sum, requires .mvn/wrapper/maven-wrapper.properties
while IFS="=" read -r key value; do
  case "${key-}" in
  distributionUrl) distributionUrl=$(trim "${value-}") ;;
  distributionSha256Sum) distributionSha256Sum=$(trim "${value-}") ;;
  esac
done <"$scriptDir/.mvn/wrapper/maven-wrapper.properties"
[ -n "${distributionUrl-}" ] || die "cannot read distributionUrl property in $scriptDir/.mvn/wrapper/maven-wrapper.properties"
```
The loop reads the properties file line by line. `IFS="="` splits each line at `=` into `key` and `value`; `read -r` keeps backslashes literal. The `case` picks out `distributionUrl` and `distributionSha256Sum` (an optional checksum) and trims them. `done <"FILE"` feeds the file into the loop. If no URL was found, the script stops with an error.

```bash
case "${distributionUrl##*/}" in
maven-mvnd-*bin.*)
  MVN_CMD=mvnd.sh _MVNW_REPO_PATTERN=/maven/mvnd/
  case "${PROCESSOR_ARCHITECTURE-}${PROCESSOR_ARCHITEW6432-}:$(uname -a)" in
  *AMD64:CYGWIN* | *AMD64:MINGW*) distributionPlatform=windows-amd64 ;;
  :Darwin*x86_64) distributionPlatform=darwin-amd64 ;;
  :Darwin*arm64) distributionPlatform=darwin-aarch64 ;;
  :Linux*x86_64*) distributionPlatform=linux-amd64 ;;
  *)
    echo "Cannot detect native platform for mvnd on $(uname)-$(uname -m), use pure java version" >&2
    distributionPlatform=linux-amd64
    ;;
  esac
  distributionUrl="${distributionUrl%-bin.*}-$distributionPlatform.zip"
  ;;
maven-mvnd-*) MVN_CMD=mvnd.sh _MVNW_REPO_PATTERN=/maven/mvnd/ ;;
*) MVN_CMD="mvn${scriptName#mvnw}" _MVNW_REPO_PATTERN=/org/apache/maven/ ;;
esac
```
The URL's last path part (`${distributionUrl##*/}` removes everything up to the last `/`) decides what is being downloaded. For `maven-mvnd-*` (the faster "Maven daemon" variant) it selects the `mvnd.sh` command and picks a platform-specific archive name from the operating system and CPU (`uname -a`). For all other URLs, the normal case, `MVN_CMD` is `mvn` plus whatever follows `mvnw` in this script's name (`${scriptName#mvnw}`), and the repository path pattern is `/org/apache/maven/`.

```bash
# apply MVNW_REPOURL and calculate MAVEN_HOME
# maven home pattern: ~/.m2/wrapper/dists/{apache-maven-<version>,maven-mvnd-<version>-<platform>}/<hash>
[ -z "${MVNW_REPOURL-}" ] || distributionUrl="$MVNW_REPOURL$_MVNW_REPO_PATTERN${distributionUrl#*"$_MVNW_REPO_PATTERN"}"
distributionUrlName="${distributionUrl##*/}"
distributionUrlNameMain="${distributionUrlName%.*}"
distributionUrlNameMain="${distributionUrlNameMain%-bin}"
MAVEN_USER_HOME="${MAVEN_USER_HOME:-${HOME}/.m2}"
MAVEN_HOME="${MAVEN_USER_HOME}/wrapper/dists/${distributionUrlNameMain-}/$(hash_string "$distributionUrl")"
```
If `MVNW_REPOURL` is set, the URL is rebuilt on that mirror. Then names are derived: the archive file name, the same without the extension and without `-bin`, the user's Maven folder (`MAVEN_USER_HOME`, default `~/.m2`), and finally `MAVEN_HOME`, the install folder `~/.m2/wrapper/dists/<name>/<hash of URL>`.

```bash
exec_maven() {
  unset MVNW_VERBOSE MVNW_USERNAME MVNW_PASSWORD MVNW_REPOURL || :
  exec "$MAVEN_HOME/bin/$MVN_CMD" "$@" || die "cannot exec $MAVEN_HOME/bin/$MVN_CMD"
}

if [ -d "$MAVEN_HOME" ]; then
  verbose "found existing MAVEN_HOME at $MAVEN_HOME"
  exec_maven "$@"
fi

case "${distributionUrl-}" in
*?-bin.zip | *?maven-mvnd-?*-?*.zip) ;;
*) die "distributionUrl is not valid, must match *-bin.zip or maven-mvnd-*.zip, but found '${distributionUrl-}'" ;;
esac
```
`exec_maven` forgets the wrapper variables (so Maven's own environment is clean) and replaces the script with the real Maven (`exec`), passing along all arguments (`"$@"`). If Maven is already installed in `MAVEN_HOME`, the script runs it and never returns. Otherwise lines 158-161 check that the URL looks valid (ends in `-bin.zip` or is an mvnd archive).

```bash
# prepare tmp dir
if TMP_DOWNLOAD_DIR="$(mktemp -d)" && [ -d "$TMP_DOWNLOAD_DIR" ]; then
  clean() { rm -rf -- "$TMP_DOWNLOAD_DIR"; }
  trap clean HUP INT TERM EXIT
else
  die "cannot create temp dir"
fi

mkdir -p -- "${MAVEN_HOME%/*}"

# Download and Install Apache Maven
verbose "Couldn't find MAVEN_HOME, downloading and installing it ..."
verbose "Downloading from: $distributionUrl"
verbose "Downloading to: $TMP_DOWNLOAD_DIR/$distributionUrlName"
```
A temporary folder is created with `mktemp -d`; `clean` deletes it and `trap clean HUP INT TERM EXIT` runs `clean` however the script ends (hang-up, Ctrl+C, terminate, or normal exit). Then the parent of `MAVEN_HOME` is created, and three `verbose` lines announce the download.

```bash
# select .zip or .tar.gz
if ! command -v unzip >/dev/null; then
  distributionUrl="${distributionUrl%.zip}.tar.gz"
  distributionUrlName="${distributionUrl##*/}"
fi

# verbose opt
__MVNW_QUIET_WGET=--quiet __MVNW_QUIET_CURL=--silent __MVNW_QUIET_UNZIP=-q __MVNW_QUIET_TAR=''
[ "${MVNW_VERBOSE-}" != true ] || __MVNW_QUIET_WGET='' __MVNW_QUIET_CURL='' __MVNW_QUIET_UNZIP='' __MVNW_QUIET_TAR=v

# normalize http auth
case "${MVNW_PASSWORD:+has-password}" in
'') MVNW_USERNAME='' MVNW_PASSWORD='' ;;
has-password) [ -n "${MVNW_USERNAME-}" ] || MVNW_USERNAME='' MVNW_PASSWORD='' ;;
esac
```
If `unzip` is missing, the script switches to the `.tar.gz` archive instead. The `__MVNW_QUIET_*` variables hold the "be quiet" flag for each tool and are emptied when verbose mode is on. The authentication block normalises the credentials: with no password both are blanked; with a password but no user name, both are blanked.

```bash
if [ -z "${MVNW_USERNAME-}" ] && command -v wget >/dev/null; then
  verbose "Found wget ... using wget"
  wget ${__MVNW_QUIET_WGET:+"$__MVNW_QUIET_WGET"} "$distributionUrl" -O "$TMP_DOWNLOAD_DIR/$distributionUrlName" || die "wget: Failed to fetch $distributionUrl"
elif [ -z "${MVNW_USERNAME-}" ] && command -v curl >/dev/null; then
  verbose "Found curl ... using curl"
  curl ${__MVNW_QUIET_CURL:+"$__MVNW_QUIET_CURL"} -f -L -o "$TMP_DOWNLOAD_DIR/$distributionUrlName" "$distributionUrl" || die "curl: Failed to fetch $distributionUrl"
elif set_java_home; then
  verbose "Falling back to use Java to download"
  javaSource="$TMP_DOWNLOAD_DIR/Downloader.java"
  targetZip="$TMP_DOWNLOAD_DIR/$distributionUrlName"
  cat >"$javaSource" <<-END
	public class Downloader extends java.net.Authenticator
	{
	  protected java.net.PasswordAuthentication getPasswordAuthentication()
	  {
	    return new java.net.PasswordAuthentication( System.getenv( "MVNW_USERNAME" ), System.getenv( "MVNW_PASSWORD" ).toCharArray() );
	  }
	  public static void main( String[] args ) throws Exception
	  {
	    setDefault( new Downloader() );
	    java.nio.file.Files.copy( java.net.URI.create( args[0] ).toURL().openStream(), java.nio.file.Paths.get( args[1] ).toAbsolutePath().normalize() );
	  }
	}
	END
  # For Cygwin/MinGW, switch paths to Windows format before running javac and java
  verbose " - Compiling Downloader.java ..."
  "$(native_path "$JAVACCMD")" "$(native_path "$javaSource")" || die "Failed to compile Downloader.java"
  verbose " - Running Downloader.java ..."
  "$(native_path "$JAVACMD")" -cp "$(native_path "$TMP_DOWNLOAD_DIR")" Downloader "$distributionUrl" "$(native_path "$targetZip")"
fi
```
The download: `wget` if available (and no credentials), else `curl` (`-f` fail on error, `-L` follow redirects, `-o` output file), else Java. The Java fallback writes a tiny `Downloader.java` program with a *here-document* (`<<-END ... END`, text up to the line `END` fed to `cat`; the `-` allows tab indentation), compiles it with `javac`, and runs it; the program uses the credentials from the environment and copies the URL's bytes to a file. Every download step is followed by `|| die` so a failure stops the script with a clear message.

```bash
# If specified, validate the SHA-256 sum of the Maven distribution zip file
if [ -n "${distributionSha256Sum-}" ]; then
  distributionSha256Result=false
  if [ "$MVN_CMD" = mvnd.sh ]; then
    echo "Checksum validation is not supported for maven-mvnd." >&2
    echo "Please disable validation by removing 'distributionSha256Sum' from your maven-wrapper.properties." >&2
    exit 1
  elif command -v sha256sum >/dev/null; then
    if echo "$distributionSha256Sum  $TMP_DOWNLOAD_DIR/$distributionUrlName" | sha256sum -c - >/dev/null 2>&1; then
      distributionSha256Result=true
    fi
  elif command -v shasum >/dev/null; then
    if echo "$distributionSha256Sum  $TMP_DOWNLOAD_DIR/$distributionUrlName" | shasum -a 256 -c >/dev/null 2>&1; then
      distributionSha256Result=true
    fi
  else
    echo "Checksum validation was requested but neither 'sha256sum' or 'shasum' are available." >&2
    echo "Please install either command, or disable validation by removing 'distributionSha256Sum' from your maven-wrapper.properties." >&2
    exit 1
  fi
  if [ $distributionSha256Result = false ]; then
    echo "Error: Failed to validate Maven distribution SHA-256, your Maven distribution might be compromised." >&2
    echo "If you updated your Maven version, you need to update the specified distributionSha256Sum property." >&2
    exit 1
  fi
fi
```
If a checksum is configured, the script computes SHA-256 of the downloaded file with `sha256sum` or `shasum -a 256` (whichever exists) by feeding `expected-hash  filename` to `-c` (check mode) and records `true` or `false`. The mvnd variant does not support this and exits. A mismatch exits with an error saying the download may be tampered with.

```bash
# unzip and move
if command -v unzip >/dev/null; then
  unzip ${__MVNW_QUIET_UNZIP:+"$__MVNW_QUIET_UNZIP"} "$TMP_DOWNLOAD_DIR/$distributionUrlName" -d "$TMP_DOWNLOAD_DIR" || die "failed to unzip"
else
  tar xzf${__MVNW_QUIET_TAR:+"$__MVNW_QUIET_TAR"} "$TMP_DOWNLOAD_DIR/$distributionUrlName" -C "$TMP_DOWNLOAD_DIR" || die "failed to untar"
fi
```
Extract with `unzip` (or `tar xzf` for the `.tar.gz` fallback) into the temporary folder.

```bash
# Find the actual extracted directory name (handles snapshots where filename != directory name)
actualDistributionDir=""

# First try the expected directory name (for regular distributions)
if [ -d "$TMP_DOWNLOAD_DIR/$distributionUrlNameMain" ]; then
  if [ -f "$TMP_DOWNLOAD_DIR/$distributionUrlNameMain/bin/$MVN_CMD" ]; then
    actualDistributionDir="$distributionUrlNameMain"
  fi
fi

# If not found, search for any directory with the Maven executable (for snapshots)
if [ -z "$actualDistributionDir" ]; then
  # enable globbing to iterate over items
  set +f
  for dir in "$TMP_DOWNLOAD_DIR"/*; do
    if [ -d "$dir" ]; then
      if [ -f "$dir/bin/$MVN_CMD" ]; then
        actualDistributionDir="$(basename "$dir")"
        break
      fi
    fi
  done
  set -f
fi
```
The archive's inner folder is normally named like the archive, but snapshot builds differ, so the script first tries the expected name (a folder that contains `bin/mvn`), and otherwise searches every folder for one that has the Maven executable. `set +f` temporarily re-enables wildcards so `"$TMP_DOWNLOAD_DIR"/*` expands; `set -f` turns them off again.

```bash
if [ -z "$actualDistributionDir" ]; then
  verbose "Contents of $TMP_DOWNLOAD_DIR:"
  verbose "$(ls -la "$TMP_DOWNLOAD_DIR")"
  die "Could not find Maven distribution directory in extracted archive"
fi

verbose "Found extracted Maven distribution directory: $actualDistributionDir"
printf %s\\n "$distributionUrl" >"$TMP_DOWNLOAD_DIR/$actualDistributionDir/mvnw.url"
mv -- "$TMP_DOWNLOAD_DIR/$actualDistributionDir" "$MAVEN_HOME" || [ -d "$MAVEN_HOME" ] || die "fail to move MAVEN_HOME"

clean || :
exec_maven "$@"
```
If nothing was found, the script lists the folder (in verbose mode) and stops. Otherwise it records the download URL in a file `mvnw.url` inside the distribution, moves the folder to `MAVEN_HOME` (tolerating another process having moved one there first), runs `clean`, and finally `exec_maven "$@"` runs Maven with the arguments you gave.

##### `mvnw.cmd`: the same job for Windows

`mvnw.cmd` is a trick file: it is a Windows batch script and a PowerShell script at the same time. The batch part at the top starts PowerShell on the file itself; PowerShell then does the real work and prints a line `MVN_CMD=<path>`; the batch part reads that line and runs the Maven it names.

```bat
<# : batch portion
@REM ----------------------------------------------------------------------------
@REM Licensed to the Apache Software Foundation (ASF) under one
@REM or more contributor license agreements.  See the NOTICE file
@REM distributed with this work for additional information
@REM regarding copyright ownership.  The ASF licenses this file
@REM to you under the Apache License, Version 2.0 (the
@REM "License"); you may not use this file except in compliance
@REM with the License.  You may obtain a copy of the License at
@REM
@REM    http://www.apache.org/licenses/LICENSE-2.0
@REM
@REM Unless required by applicable law or agreed to in writing,
@REM software distributed under the License is distributed on an
@REM "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
@REM KIND, either express or implied.  See the License for the
@REM specific language governing permissions and limitations
@REM under the License.
@REM ----------------------------------------------------------------------------
```
Line 1 begins `<#`, which PowerShell reads as the start of a block comment and the batch interpreter treats as a harmless unknown line. `@REM` is the batch comment word (the `@` stops the line being echoed). Lines 2-19 are the license text.

```bat
@REM ----------------------------------------------------------------------------
@REM Apache Maven Wrapper startup batch script, version 3.3.4
@REM
@REM Optional ENV vars
@REM   MVNW_REPOURL - repo url base for downloading maven distribution
@REM   MVNW_USERNAME/MVNW_PASSWORD - user and password for downloading maven
@REM   MVNW_VERBOSE - true: enable verbose log; others: silence the output
@REM ----------------------------------------------------------------------------

@IF "%__MVNW_ARG0_NAME__%"=="" (SET __MVNW_ARG0_NAME__=%~nx0)
@SET __MVNW_CMD__=
@SET __MVNW_ERROR__=
@SET __MVNW_PSMODULEP_SAVE=%PSModulePath%
@SET PSModulePath=
@FOR /F "usebackq tokens=1* delims==" %%A IN (`powershell -noprofile "& {$scriptDir='%~dp0'; $script='%__MVNW_ARG0_NAME__%'; icm -ScriptBlock ([Scriptblock]::Create((Get-Content -Raw '%~f0'))) -NoNewScope}"`) DO @(
  IF "%%A"=="MVN_CMD" (set __MVNW_CMD__=%%B) ELSE IF "%%B"=="" (echo %%A) ELSE (echo %%A=%%B)
)
@SET PSModulePath=%__MVNW_PSMODULEP_SAVE%
@SET __MVNW_PSMODULEP_SAVE=
@SET __MVNW_ARG0_NAME__=
@SET MVNW_USERNAME=
@SET MVNW_PASSWORD=
@IF NOT "%__MVNW_CMD__%"=="" ("%__MVNW_CMD__%" %*)
@echo Cannot start maven from wrapper >&2 && exit /b 1
@GOTO :EOF
: end batch / begin powershell #>
```
`SET NAME=value` sets a variable. The script remembers its own name (`%~nx0` is this file's name and extension), clears two variables, and temporarily empties `PSModulePath` (so PowerShell does not load modules from a user's environment). The `FOR /F ... IN (`powershell ...`)` line runs PowerShell with the whole file contents as a script block (`Get-Content -Raw '%~f0'` reads this file; `%~dp0` is its folder) and processes each line of output split at `=`: if the key is `MVN_CMD` its value is saved; any other line is echoed. The lines after restore the saved variables, forget the download credentials, and run the chosen Maven with all arguments (`%*`). If that was not possible the script prints "Cannot start maven from wrapper" to standard error and exits 1. `GOTO :EOF` jumps to the end of the batch part. Line 46, `: end batch / begin powershell #>`, closes the PowerShell comment.

```bat
$ErrorActionPreference = "Stop"
if ($env:MVNW_VERBOSE -eq "true") {
  $VerbosePreference = "Continue"
}

# calculate distributionUrl, requires .mvn/wrapper/maven-wrapper.properties
$distributionUrl = (Get-Content -Raw "$scriptDir/.mvn/wrapper/maven-wrapper.properties" | ConvertFrom-StringData).distributionUrl
if (!$distributionUrl) {
  Write-Error "cannot read distributionUrl property in $scriptDir/.mvn/wrapper/maven-wrapper.properties"
}

switch -wildcard -casesensitive ( $($distributionUrl -replace '^.*/','') ) {
  "maven-mvnd-*" {
    $USE_MVND = $true
    $distributionUrl = $distributionUrl -replace '-bin\.[^.]*$',"-windows-amd64.zip"
    $MVN_CMD = "mvnd.cmd"
    break
  }
  default {
    $USE_MVND = $false
    $MVN_CMD = $script -replace '^mvnw','mvn'
    break
  }
}
```
PowerShell starts here. `$ErrorActionPreference = "Stop"` makes any error end the script. Verbose output is enabled by `MVNW_VERBOSE`. The properties file is read with `ConvertFrom-StringData`, which turns `key=value` text into a table, and the URL is taken from it. A `switch -wildcard` on the archive's name selects the mvnd variant (and rewrites the URL to the Windows archive) or the normal case, where the command name is the script name with `mvnw` replaced by `mvn`.

```bat
# apply MVNW_REPOURL and calculate MAVEN_HOME
# maven home pattern: ~/.m2/wrapper/dists/{apache-maven-<version>,maven-mvnd-<version>-<platform>}/<hash>
if ($env:MVNW_REPOURL) {
  $MVNW_REPO_PATTERN = if ($USE_MVND -eq $False) { "/org/apache/maven/" } else { "/maven/mvnd/" }
  $distributionUrl = "$env:MVNW_REPOURL$MVNW_REPO_PATTERN$($distributionUrl -replace "^.*$MVNW_REPO_PATTERN",'')"
}
$distributionUrlName = $distributionUrl -replace '^.*/',''
$distributionUrlNameMain = $distributionUrlName -replace '\.[^.]*$','' -replace '-bin$',''

$MAVEN_M2_PATH = "$HOME/.m2"
if ($env:MAVEN_USER_HOME) {
  $MAVEN_M2_PATH = "$env:MAVEN_USER_HOME"
}

if (-not (Test-Path -Path $MAVEN_M2_PATH)) {
    New-Item -Path $MAVEN_M2_PATH -ItemType Directory | Out-Null
}

$MAVEN_WRAPPER_DISTS = $null
if ((Get-Item $MAVEN_M2_PATH).Target[0] -eq $null) {
  $MAVEN_WRAPPER_DISTS = "$MAVEN_M2_PATH/wrapper/dists"
} else {
  $MAVEN_WRAPPER_DISTS = (Get-Item $MAVEN_M2_PATH).Target[0] + "/wrapper/dists"
}

$MAVEN_HOME_PARENT = "$MAVEN_WRAPPER_DISTS/$distributionUrlNameMain"
$MAVEN_HOME_NAME = ([System.Security.Cryptography.SHA256]::Create().ComputeHash([byte[]][char[]]$distributionUrl) | ForEach-Object {$_.ToString("x2")}) -join ''
$MAVEN_HOME = "$MAVEN_HOME_PARENT/$MAVEN_HOME_NAME"
```
The optional mirror is applied. The archive names are derived with `-replace`, which applies a regular expression. The Maven user folder is `~/.m2` unless `MAVEN_USER_HOME` is set; it is created if missing, and if it is a symbolic link its target is used. Unlike `mvnw`, the install folder name here is the SHA-256 hash of the URL, computed by turning the text into bytes, hashing it, and writing each byte as two hexadecimal digits.

```bat
if (Test-Path -Path "$MAVEN_HOME" -PathType Container) {
  Write-Verbose "found existing MAVEN_HOME at $MAVEN_HOME"
  Write-Output "MVN_CMD=$MAVEN_HOME/bin/$MVN_CMD"
  exit $?
}

if (! $distributionUrlNameMain -or ($distributionUrlName -eq $distributionUrlNameMain)) {
  Write-Error "distributionUrl is not valid, must end with *-bin.zip, but found $distributionUrl"
}
```
If Maven is already installed, it prints `MVN_CMD=<path>` for the batch part and exits. The check on line 108 rejects URLs that do not end in `-bin.zip`.

```bat
# prepare tmp dir
$TMP_DOWNLOAD_DIR_HOLDER = New-TemporaryFile
$TMP_DOWNLOAD_DIR = New-Item -Itemtype Directory -Path "$TMP_DOWNLOAD_DIR_HOLDER.dir"
$TMP_DOWNLOAD_DIR_HOLDER.Delete() | Out-Null
trap {
  if ($TMP_DOWNLOAD_DIR.Exists) {
    try { Remove-Item $TMP_DOWNLOAD_DIR -Recurse -Force | Out-Null }
    catch { Write-Warning "Cannot remove $TMP_DOWNLOAD_DIR" }
  }
}

New-Item -Itemtype Directory -Path "$MAVEN_HOME_PARENT" -Force | Out-Null

# Download and Install Apache Maven
Write-Verbose "Couldn't find MAVEN_HOME, downloading and installing it ..."
Write-Verbose "Downloading from: $distributionUrl"
Write-Verbose "Downloading to: $TMP_DOWNLOAD_DIR/$distributionUrlName"

$webclient = New-Object System.Net.WebClient
if ($env:MVNW_USERNAME -and $env:MVNW_PASSWORD) {
  $webclient.Credentials = New-Object System.Net.NetworkCredential($env:MVNW_USERNAME, $env:MVNW_PASSWORD)
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$webclient.DownloadFile($distributionUrl, "$TMP_DOWNLOAD_DIR/$distributionUrlName") | Out-Null
```
A temporary file is created and turned into a temporary folder; the `trap` block deletes the folder if an error occurs. The install parent folder is created, then the archive is downloaded with a .NET `WebClient` (with credentials if both variables are set, using TLS 1.2).

```bat
# If specified, validate the SHA-256 sum of the Maven distribution zip file
$distributionSha256Sum = (Get-Content -Raw "$scriptDir/.mvn/wrapper/maven-wrapper.properties" | ConvertFrom-StringData).distributionSha256Sum
if ($distributionSha256Sum) {
  if ($USE_MVND) {
    Write-Error "Checksum validation is not supported for maven-mvnd. `nPlease disable validation by removing 'distributionSha256Sum' from your maven-wrapper.properties."
  }
  Import-Module $PSHOME\Modules\Microsoft.PowerShell.Utility -Function Get-FileHash
  if ((Get-FileHash "$TMP_DOWNLOAD_DIR/$distributionUrlName" -Algorithm SHA256).Hash.ToLower() -ne $distributionSha256Sum) {
    Write-Error "Error: Failed to validate Maven distribution SHA-256, your Maven distribution might be compromised. If you updated your Maven version, you need to update the specified distributionSha256Sum property."
  }
}

# unzip and move
Expand-Archive "$TMP_DOWNLOAD_DIR/$distributionUrlName" -DestinationPath "$TMP_DOWNLOAD_DIR" | Out-Null
```
Checksum validation, as in the shell version: read the expected value, refuse for mvnd, compute the file's SHA-256 with `Get-FileHash`, lower-case it and compare. Then `Expand-Archive` unzips.

```bat
# Find the actual extracted directory name (handles snapshots where filename != directory name)
$actualDistributionDir = ""

# First try the expected directory name (for regular distributions)
$expectedPath = Join-Path "$TMP_DOWNLOAD_DIR" "$distributionUrlNameMain"
$expectedMvnPath = Join-Path "$expectedPath" "bin/$MVN_CMD"
if ((Test-Path -Path $expectedPath -PathType Container) -and (Test-Path -Path $expectedMvnPath -PathType Leaf)) {
  $actualDistributionDir = $distributionUrlNameMain
}

# If not found, search for any directory with the Maven executable (for snapshots)
if (!$actualDistributionDir) {
  Get-ChildItem -Path "$TMP_DOWNLOAD_DIR" -Directory | ForEach-Object {
    $testPath = Join-Path $_.FullName "bin/$MVN_CMD"
    if (Test-Path -Path $testPath -PathType Leaf) {
      $actualDistributionDir = $_.Name
    }
  }
}

if (!$actualDistributionDir) {
  Write-Error "Could not find Maven distribution directory in extracted archive"
}

Write-Verbose "Found extracted Maven distribution directory: $actualDistributionDir"
Rename-Item -Path "$TMP_DOWNLOAD_DIR/$actualDistributionDir" -NewName $MAVEN_HOME_NAME | Out-Null
try {
  Move-Item -Path "$TMP_DOWNLOAD_DIR/$MAVEN_HOME_NAME" -Destination $MAVEN_HOME_PARENT | Out-Null
} catch {
  if (! (Test-Path -Path "$MAVEN_HOME" -PathType Container)) {
    Write-Error "fail to move MAVEN_HOME"
  }
} finally {
  try { Remove-Item $TMP_DOWNLOAD_DIR -Recurse -Force | Out-Null }
  catch { Write-Warning "Cannot remove $TMP_DOWNLOAD_DIR" }
}

Write-Output "MVN_CMD=$MAVEN_HOME/bin/$MVN_CMD"
```
Find the extracted folder (expected name first, then any folder containing `bin/mvn...`), fail if none, rename it to the hash name, move it into place (an error is tolerated if another process already created it) and always try to delete the temporary folder in the `finally` block. The last line prints `MVN_CMD=<path>/bin/<command>`, which the batch part executes.
<!-- full-walkthrough:end -->

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
