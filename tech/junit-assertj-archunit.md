# JUnit 5, AssertJ and ArchUnit

## 1. What it is

**JUnit** is the standard Java test framework: a method marked `@Test` is a test. **AssertJ** adds readable assertions (`assertThat(x).isEqualTo(y)`). **ArchUnit** tests the *structure* of the code (which packages may use which) as ordinary tests.

## 2. Why this repository uses it

The pipeline publishes JUnit XML reports, so the lesson needs real tests: 33 unit tests, 9 integration tests, and an architecture test that keeps the layers honest.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `app/src/test/java/.../domain/MoneyTest.java, OrderTest.java` | unit tests of the domain (parameterized) |
| `app/src/test/java/.../application/SummarizeOrdersTest.java` | unit tests of the use case with an in-line source |
| `app/src/test/java/.../infrastructure/CsvOrderSourceIT.java` | integration test over real files |
| `app/src/test/java/.../interfaces/MainIT.java` | integration test of the command line |
| `app/src/test/java/.../ArchitectureTest.java` | ArchUnit rules |
| `app/src/test/java/.../PipelineSwitchTest.java` | the test that fails on demand |
| `app/pom.xml` | junit-jupiter 6.1.3, assertj-core 3.27.7, archunit-junit5 1.5.1 (test scope) |

## 4. How it works underneath

- Tests whose names end in `Test` run in the **unit** phase (Surefire); those ending in `IT` run as **integration** tests (Failsafe).
- `@ParameterizedTest` runs one method for many inputs: `@CsvSource({"0,0", "7,700"})` supplies rows, `@ValueSource(strings = {...})` supplies single values.
- `@TempDir Path directory;` gives each test a fresh temporary folder that is deleted afterwards.
- AssertJ reads left to right: `assertThatThrownBy(() -> Money.parse("abc")).isInstanceOf(InvalidOrderException.class).hasMessageContaining("not an amount")`.
- ArchUnit imports compiled classes and checks rules such as "no class in `..domain..` depends on a class in `..application..`".

## 5. Walkthrough of this repository's use

### A parameterized unit test (`MoneyTest`)
```java
@ParameterizedTest
@CsvSource({"0,0", "7,700", "12.5,1250", "12.50,1250", "0.07,7", "1000000.99,100000099"})
void parses_decimal_amounts_into_cents(String text, long cents) {
    assertThat(Money.parse(text).cents()).isEqualTo(cents);
}
@ParameterizedTest
@ValueSource(strings = {"", "abc", "-1", "1.234", "1,5", "1.", ".5"})
void rejects_text_that_is_not_an_amount(String text) {
    assertThatThrownBy(() -> Money.parse(text)).isInstanceOf(InvalidOrderException.class).hasMessageContaining("not an amount");
}
```
Each CSV row runs the method once: text in, expected cents out. The second test runs seven times, once per bad input. The lambda `() -> Money.parse(text)` delays the call so AssertJ can catch the exception.

### `SummarizeOrdersTest`
`new SummarizeOrders(() -> List.of(orders)).run()`: `OrderSource` has one method, so a lambda is a complete test double (no mocking library). Tests: totals paid and shipped orders per customer; ignores placed and cancelled; sorts by revenue then customer id; empty in, empty out.

### Integration tests (`*IT`)
`CsvOrderSourceIT` writes real CSV files into a `@TempDir` and reads them: valid file, blank lines skipped, missing header refused, a bad line reported with its line number, wrong field count reported, missing file becomes `UncheckedIOException`. `MainIT` calls `Main.run(args, out, err)` with `PrintStream`s that write to byte arrays: it checks the exact report lines, exit code 2 with a message for bad input, usage text when the argument is missing, and exit code 2 for a file that does not exist.

### `ArchitectureTest`
```java
@AnalyzeClasses(packages = "dev.plainround.orders", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {
    @ArchTest
    static final ArchRule DOMAIN_DEPENDS_ON_NOTHING_ELSE_IN_THE_PROJECT = noClasses().that()
            .resideInAPackage("..domain..").should().dependOnClassesThat()
            .resideInAnyPackage("..application..", "..infrastructure..", "..interfaces..");
```
`..domain..` means "the package `domain` at any depth". Four rules: the domain depends on nothing else here; the application does not know infrastructure or interfaces; nothing outside `interfaces` depends on it; infrastructure does not depend on interfaces. A future change that breaks the layering fails this test.

### `PipelineSwitchTest`
```java
assertThat(System.getenv("BREAK_A_TEST")).as("BREAK_A_TEST was set to true by the pipeline's parameter").isNotEqualTo("true");
```
Passes unless the environment variable is `true`: the pipeline's `BREAK_A_TEST` parameter makes exactly one test fail, which shows how Jenkins reports a failure.

## 6. Try it yourself

1. `cd app && ./mvnw --batch-mode --no-transfer-progress surefire:test` : 33 unit tests.
2. `./mvnw --batch-mode --no-transfer-progress failsafe:integration-test failsafe:verify` : 9 integration tests.
3. `ls target/surefire-reports | head` and `head -5 target/surefire-reports/TEST-*MoneyTest.xml` : the XML Jenkins publishes.
4. Add `import dev.plainround.orders.infrastructure.CsvOrderSource;` to `Money.java` and run `./mvnw surefire:test` : the architecture rule fails (revert it afterwards).
5. `BREAK_A_TEST=true ./mvnw surefire:test` : one failure, `PipelineSwitchTest`.

## 7. Mistakes people make

- A test that depends on test order or on files it did not create. `@TempDir` gives each test its own folder.
- Mocking everything. Here a lambda is a hand-made fake of a one-method interface.
- Asserting only that no exception happened. Each test also checks a value or a message.

## 8. Check yourself

1. How does Maven tell unit tests from integration tests here?
   *Answer:* By name: `*Test` (Surefire) versus `*IT` (Failsafe).
2. What does `@TempDir` give a test?
   *Answer:* A fresh temporary folder, deleted afterwards.
3. What does ArchUnit test?
   *Answer:* Dependencies between packages, as code.
4. Why is `Main.run` tested instead of `main`?
   *Answer:* `main` ends the JVM; `run` returns an exit code.
5. What does `@CsvSource` do?
   *Answer:* Runs a test once per row of inputs.

## 9. Further reading

- JUnit 5/6 user guide: <https://docs.junit.org/> (this repository pins `junit-jupiter` 6.1.3). AssertJ: <https://assertj.github.io/doc/> (3.27.7). ArchUnit: <https://www.archunit.org/userguide/html/000_Index.html> (1.5.1). The JUnit 6 site layout was not re-checked in this session.
