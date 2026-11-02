# JaCoCo and Checkstyle

## 1. What it is

**JaCoCo** measures which lines of code the tests ran (code coverage) and can fail a build under a threshold. **Checkstyle** checks Java source against style rules (imports, braces, naming, line length, Javadoc).

## 2. Why this repository uses it

The pipeline has a `Lint` stage (Checkstyle) and a `Coverage` stage (JaCoCo's rule). They are the stages that show a gate failing for a reason other than a broken test.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `app/pom.xml` | both plugin configurations |
| `app/config/checkstyle/checkstyle.xml` | the rule set |
| `Jenkinsfile` | `Lint` and `Coverage` stages |

## 4. How it works underneath

- JaCoCo works with a **Java agent**: a JVM option (`-javaagent:...`) that records which instructions run, into a binary file (`jacoco-unit.exec`). `report` turns it into HTML/XML; `check` applies rules to it.
- A *counter* is what is counted (`LINE`, `BRANCH`); a *value* is how (`COVEREDRATIO` is covered / total).
- Checkstyle rules are modules in an XML tree: a `TreeWalker` module contains the checks that look at the syntax tree.

## 5. Walkthrough of this repository's use

### JaCoCo
The three executions in the POM are explained in the Maven note: `agent` writes `target/jacoco-unit.exec` for the unit tests only; `report` writes the HTML report; `coverage` fails the build unless the packages `dev.plainround.orders.domain` and `dev.plainround.orders.application` have at least **95 percent** line coverage. The Jenkinsfile's `Coverage` stage runs `test -f target/jacoco-unit.exec && ./mvnw jacoco:report@report jacoco:check@coverage` because JaCoCo **skips quietly** when the data file is missing: without the `test -f` a build could pass coverage on no data.

### Checkstyle (`config/checkstyle/checkstyle.xml`)
The modules it enables: `NewlineAtEndOfFile`, `FileTabCharacter` (no tabs), `LineLength`, then under `TreeWalker`: `AvoidStarImport`, `UnusedImports`, `RedundantImport`, `NeedBraces` (an `if` always has braces), `EmptyStatement`, `EqualsHashCode`, `MissingSwitchDefault`, `ModifierOrder`, `UpperEll` (`100L`, not `100l`), `TypeName`, `MethodName`, `ConstantName`, `LocalVariableName`, `ParameterName`, `MissingJavadocType`. The POM sets `includeTestSourceDirectory` true (tests are checked too) and `violationSeverity` to `warning`, so any finding fails `checkstyle:check`. That is why every public class and method in `src/main` has a Javadoc comment, and why test methods use `snake_case` descriptions only where the config allows.




<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: `app/config/checkstyle/checkstyle.xml`

Checkstyle is a program that reads Java source and reports style and rule violations. Its configuration is a tree of `module` elements: a `Checker` that looks at whole files, and inside it a `TreeWalker` that visits the syntax tree of each file and runs the *checks* listed inside it. A module's `property` tag changes its settings. JaCoCo's configuration is covered in `maven.md`.

```xml
<?xml version="1.0"?>
<!DOCTYPE module PUBLIC "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN" "https://checkstyle.org/dtds/configuration_1_3.dtd">
<module name="Checker">
  <property name="severity" value="warning"/>
  <property name="charset" value="UTF-8"/>
```
Line 1 is the XML declaration. Line 2 is a `DOCTYPE`, a pointer to the format definition (DTD) that Checkstyle files follow. `Checker` is the outer module. Its `severity` property `warning` marks every finding as a warning (the pom then fails the build on warnings), and `charset` says the files are UTF-8.

```xml
  <module name="NewlineAtEndOfFile"/>
  <module name="FileTabCharacter"/>
  <module name="LineLength">
    <property name="max" value="140"/>
  </module>
```
File-level checks: `NewlineAtEndOfFile` requires the last line to end with a newline; `FileTabCharacter` forbids tab characters; `LineLength` with `max` 140 limits line length.

```xml
  <module name="TreeWalker">
    <module name="AvoidStarImport"/>
    <module name="UnusedImports"/>
    <module name="RedundantImport"/>
    <module name="NeedBraces"/>
    <module name="EmptyStatement"/>
    <module name="EqualsHashCode"/>
    <module name="MissingSwitchDefault"/>
    <module name="ModifierOrder"/>
    <module name="UpperEll"/>
    <module name="TypeName"/>
    <module name="MethodName">
      <!-- snake_case test names are allowed in test classes only; main code is lowerCamelCase -->
      <property name="format" value="^[a-z][a-zA-Z0-9_]*$"/>
    </module>
    <module name="ConstantName"/>
    <module name="LocalVariableName"/>
    <module name="ParameterName"/>
    <module name="MissingJavadocType">
      <property name="scope" value="public"/>
    </module>
  </module>
</module>
```
`TreeWalker` checks, one per line: `AvoidStarImport` forbids `import x.*`; `UnusedImports` and `RedundantImport` find imports that are not needed; `NeedBraces` demands `{ }` after every `if`/`for`; `EmptyStatement` flags a stray `;`; `EqualsHashCode` requires that a class defining `equals` also defines `hashCode`; `MissingSwitchDefault` requires a `default` branch in a `switch`; `ModifierOrder` enforces the standard order of words like `public static final`; `UpperEll` requires `100L` not `100l`; `TypeName`, `ConstantName`, `LocalVariableName`, `ParameterName` enforce naming style; `MethodName` is configured with its own regular expression (the comment explains: underscores are allowed so test methods can be written in readable snake case); `MissingJavadocType` with scope `public` requires a documentation comment on every public class.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `cd app && ./mvnw --batch-mode --no-transfer-progress checkstyle:check` : `You have 0 Checkstyle violations`.
2. Add an unused import to a class and rerun : a violation naming `UnusedImports`.
3. `./mvnw --batch-mode jacoco:prepare-agent@agent surefire:test jacoco:report@report` then open `target/site/jacoco/index.html` : the report.
4. Raise `<minimum>` to `1.00` in a copy of the POM and run `jacoco:check@coverage` : the rule fails and prints the ratio.
5. `ls app/target/jacoco-unit.exec` : the data file.

## 7. Mistakes people make

- A coverage gate that passes on no data. Here the file must exist first.
- Chasing 100 percent: the rule covers the domain and application packages, where logic lives, not the command-line glue.
- Checkstyle violations as warnings nobody reads. Here they fail the build.

## 8. Check yourself

1. How does JaCoCo see which lines ran?
   *Answer:* A Java agent records executed instructions into an `.exec` file.
2. Why test for the `.exec` file before `jacoco:check`?
   *Answer:* JaCoCo skips silently when it has no data.
3. Which packages does the 95 percent rule cover?
   *Answer:* `domain` and `application`.
4. What makes a Checkstyle finding fail the build?
   *Answer:* `violationSeverity` set to `warning`.
5. Why do unit and integration tests not share the JaCoCo file?
   *Answer:* They run in parallel and would overwrite each other.

## 9. Further reading

- JaCoCo: <https://www.jacoco.org/jacoco/trunk/doc/> (0.8.16). Checkstyle: <https://checkstyle.org/> (14.3.0; module list: <https://checkstyle.org/checks.html>).
