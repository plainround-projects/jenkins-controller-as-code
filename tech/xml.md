# XML

## 1. What it is

XML is a text format of nested **elements** written `<name>content</name>`, optionally with **attributes** (`<testsuite tests="12">`). Maven's POM, Checkstyle's rules and JUnit's test reports are XML.

## 2. Why this repository uses it

Three files you must be able to read: the POM, `checkstyle.xml`, and the reports Jenkins publishes (`TEST-*.xml`). One script (`test-summary.sh`) reads the reports without an XML library.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `app/pom.xml` | the build description |
| `app/config/checkstyle/checkstyle.xml` | style rules |
| `app/target/surefire-reports/TEST-*.xml, failsafe-reports` | test results produced by the build |
| `pipeline/scripts/test-summary.sh` | reads the attributes of `<testsuite>` |

## 4. How it works underneath

- An element has a name, optional attributes, and children or text. Every opening tag has a closing tag (`<a/>` is an empty element).
- The first line `<?xml version="1.0" encoding="UTF-8"?>` is the declaration.
- Namespaces (`xmlns="http://maven.apache.org/POM/4.0.0"`) say which vocabulary the elements belong to; `xsi:schemaLocation` points at the schema that describes them.
- Special characters are written `&lt;` `&gt;` `&amp;`.
- A JUnit report has one `<testsuite name=... tests="N" failures="F" errors="E" skipped="S">` per test class and one `<testcase>` per test (with a `<failure>` child when it failed).

## 5. Walkthrough of this repository's use

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="..." xsi:schemaLocation="...">
  <modelVersion>4.0.0</modelVersion>
  <groupId>dev.plainround</groupId>
  <artifactId>order-summary</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>
```
The root element `<project>` declares Maven's namespace and schema. The next lines are the project's coordinates and that it is packaged as a jar. Other elements: `<properties>` (variables), `<dependencies>` (each `<dependency>` has `groupId`, `artifactId`, `version`, `scope`) and `<build>` with `<plugins>`. In Maven, XML nesting is meaning: a `<configuration>` inside a `<plugin>` belongs to that plugin; inside an `<execution>` it belongs to that execution only (the JaCoCo `destFile`).

Checkstyle's file:
```xml
<module name="Checker">
  <module name="NewlineAtEndOfFile"/>
  <module name="TreeWalker">
    <module name="AvoidStarImport"/>
```
Modules nest like a tree; `<property name="..." value="..."/>` children configure one module.

`test-summary.sh` reads this line of a report:
```xml
<testsuite name="dev.plainround.orders.domain.MoneyTest" tests="15" skipped="0" failures="0" errors="0" ...>
```
`grep -m1 -o '<testsuite [^>]*'` cuts the opening tag; `grep -o ' tests="[0-9]*"'` takes one attribute. This is a small, deliberate shortcut: it works because these reports put the counts on the first tag.

## 6. Try it yourself

1. `head -12 app/pom.xml` : the root and the coordinates.
2. `grep -n '<artifactId>' app/pom.xml | head -20` : every plugin and library by name.
3. `head -3 app/target/surefire-reports/TEST-dev.plainround.orders.domain.MoneyTest.xml` (after a build) : the `<testsuite ...>` line.
4. `xmllint --noout app/pom.xml` (if `xmllint` exists) : no output means well-formed.
5. `pipeline/scripts/test-summary.sh app/target/surefire-reports` : totals.

## 7. Mistakes people make

- Forgetting a closing tag or an escaped `&`.
- Using the wrong nesting (a plugin `configuration` outside the `plugin`).
- Parsing XML with regular expressions in general. The summary script accepts that only because the report format is fixed.

## 8. Check yourself

1. What is an attribute?
   *Answer:* A `name="value"` pair inside an opening tag.
2. Why does nesting matter in a POM?
   *Answer:* Where a `<configuration>` sits decides what it configures.
3. What is `xmlns`?
   *Answer:* A namespace: which vocabulary the elements belong to.
4. Where do JUnit's counts appear?
   *Answer:* As attributes on `<testsuite>`.
5. How is `&` written in XML text?
   *Answer:* `&amp;`.

## 9. Further reading

- XML 1.0: <https://www.w3.org/TR/xml/>. POM reference: <https://maven.apache.org/pom.html>.
