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



<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every Java test file

**Terms.** *JUnit* (Jupiter) is the test framework: a method marked `@Test` is a test; it passes unless it throws. `@ParameterizedTest` runs one method many times with different inputs from `@CsvSource` (rows of comma-separated values) or `@ValueSource`. *AssertJ* gives fluent checks: `assertThat(actual).isEqualTo(expected)`; `assertThatThrownBy(() -> code).isInstanceOf(X.class).hasMessageContaining("text")` asserts that code throws. `import static` lets you write the method name without the class. *ArchUnit* checks the structure of the compiled classes. In Java a **lambda** `() -> code` is a small anonymous function. Test names use snake_case words as sentences; the Checkstyle `MethodName` setting allows underscores for that.

#### `ArchitectureTest.java`: the dependency rule

```java
package dev.plainround.orders;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

/** The dependency rule: domain depends on nothing; application on domain; nothing depends on interfaces. */
@AnalyzeClasses(packages = "dev.plainround.orders", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    @ArchTest
    static final ArchRule DOMAIN_DEPENDS_ON_NOTHING_ELSE_IN_THE_PROJECT = noClasses().that()
            .resideInAPackage("..domain..").should().dependOnClassesThat()
            .resideInAnyPackage("..application..", "..infrastructure..", "..interfaces..");

    @ArchTest
    static final ArchRule APPLICATION_DOES_NOT_KNOW_INFRASTRUCTURE_OR_INTERFACES = noClasses().that()
            .resideInAPackage("..application..").should().dependOnClassesThat()
            .resideInAnyPackage("..infrastructure..", "..interfaces..");

    @ArchTest
    static final ArchRule NOTHING_DEPENDS_ON_INTERFACES = noClasses().that()
            .resideOutsideOfPackage("..interfaces..").should().dependOnClassesThat()
            .resideInAPackage("..interfaces..");

    @ArchTest
    static final ArchRule INFRASTRUCTURE_DOES_NOT_DEPEND_ON_INTERFACES = noClasses().that()
            .resideInAPackage("..infrastructure..").should().dependOnClassesThat()
            .resideInAPackage("..interfaces..");
}
```
`@AnalyzeClasses` tells ArchUnit to load the classes of the package `dev.plainround.orders`, leaving out test classes. Each `@ArchTest static final ArchRule` is a rule built with a readable chain: "no classes that reside in a package named `..domain..` should depend on classes that reside in `..application..`, `..infrastructure..` or `..interfaces..`" (`..` in a pattern means "any number of package levels"). The four rules encode the layers: domain depends on nothing else in the project; application does not know infrastructure or interfaces; nothing outside `interfaces` depends on it; infrastructure does not depend on interfaces. A change that breaks the layering fails the build.

#### `PipelineSwitchTest.java`: a deliberate switch for a demonstration

```java
package dev.plainround.orders;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/**
 * A switch for the pipeline's own demonstration: with {@code BREAK_A_TEST=true} in the environment this test fails,
 * which shows how Jenkins reports a failing test (the report is published, the build goes red, nothing is archived).
 */
class PipelineSwitchTest {

    @Test
    void the_pipeline_did_not_ask_for_a_failing_test() {
        assertThat(System.getenv("BREAK_A_TEST")).as("BREAK_A_TEST was set to true by the pipeline's parameter").isNotEqualTo("true");
    }
}
```
The Jenkinsfile passes the `BREAK_A_TEST` parameter as an environment variable. This test reads it with `System.getenv` and asserts it is *not* the text `true`, giving a controlled way to show a failing test in the build report. `.as("...")` sets the message shown on failure.

#### `domain/MoneyTest.java`

```java
package dev.plainround.orders.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

class MoneyTest {

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

    @Test
    void rejects_a_negative_amount() {
        assertThatThrownBy(() -> new Money(-1)).isInstanceOf(InvalidOrderException.class);
    }

    @Test
    void adds_amounts_and_prints_them_with_two_decimals() {
        assertThat(Money.parse("1.05").plus(Money.parse("2.10"))).hasToString("3.15");
        assertThat(Money.ZERO).hasToString("0.00");
    }

    @Test
    void orders_by_amount() {
        assertThat(Money.parse("2")).isGreaterThan(Money.parse("1.99"));
    }

    @Test
    void refuses_to_overflow() {
        assertThatThrownBy(() -> new Money(Long.MAX_VALUE).plus(new Money(1))).isInstanceOf(ArithmeticException.class);
    }
}
```
The first test checks six text/cents pairs (`12.5` and `12.50` both give 1250; `0.07` gives 7). The second feeds seven invalid texts (empty, letters, negative, three decimals, a comma, a trailing dot, no leading digit) and requires `InvalidOrderException` with "not an amount". Other tests: a negative amount is rejected; `1.05 + 2.10` prints `3.15` and zero prints `0.00` (`hasToString`); amounts sort by value; adding one to the largest `long` throws `ArithmeticException`.

#### `domain/OrderTest.java`

```java
package dev.plainround.orders.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class OrderTest {

    @Test
    void an_order_needs_an_id_and_a_customer() {
        assertThatThrownBy(() -> new Order(" ", "c1", Money.ZERO, OrderStatus.PAID))
                .isInstanceOf(InvalidOrderException.class).hasMessageContaining("needs an id");
        assertThatThrownBy(() -> new Order("o1", "", Money.ZERO, OrderStatus.PAID))
                .isInstanceOf(InvalidOrderException.class).hasMessageContaining("needs a customer");
    }

    @Test
    void an_order_needs_a_total_and_a_status() {
        assertThatThrownBy(() -> new Order("o1", "c1", null, OrderStatus.PAID)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new Order("o1", "c1", Money.ZERO, null)).isInstanceOf(NullPointerException.class);
    }

    @ParameterizedTest
    @CsvSource({"paid,true", "SHIPPED,true", " Placed ,false", "cancelled,false"})
    void only_paid_and_shipped_orders_count_as_revenue(String text, boolean counts) {
        assertThat(OrderStatus.parse(text).countsAsRevenue()).isEqualTo(counts);
    }

    @Test
    void an_unknown_status_is_named() {
        assertThatThrownBy(() -> OrderStatus.parse("lost")).isInstanceOf(InvalidOrderException.class).hasMessageContaining("'lost'");
    }
}
```
Blank id and blank customer give the two exact messages; a null total or status throws `NullPointerException`; four status spellings (different case, extra spaces) parse and only PAID and SHIPPED count as revenue; an unknown status names the bad text in quotes.

#### `application/SummarizeOrdersTest.java`

```java
package dev.plainround.orders.application;

import static org.assertj.core.api.Assertions.assertThat;

import dev.plainround.orders.domain.CustomerSummary;
import dev.plainround.orders.domain.Money;
import dev.plainround.orders.domain.Order;
import dev.plainround.orders.domain.OrderStatus;
import java.util.List;
import org.junit.jupiter.api.Test;

class SummarizeOrdersTest {

    private static Order order(String id, String customer, String amount, OrderStatus status) {
        return new Order(id, customer, Money.parse(amount), status);
    }

    private static List<CustomerSummary> summarize(Order... orders) {
        return new SummarizeOrders(() -> List.of(orders)).run();
    }

    @Test
    void totals_paid_and_shipped_orders_per_customer() {
        List<CustomerSummary> summaries = summarize(
                order("o1", "ada", "10.00", OrderStatus.PAID),
                order("o2", "ada", "5.50", OrderStatus.SHIPPED),
                order("o3", "grace", "3.00", OrderStatus.PAID));

        assertThat(summaries).containsExactly(
                new CustomerSummary("ada", 2, Money.parse("15.50")),
                new CustomerSummary("grace", 1, Money.parse("3.00")));
    }

    @Test
    void ignores_placed_and_cancelled_orders() {
        assertThat(summarize(
                order("o1", "ada", "10.00", OrderStatus.PLACED),
                order("o2", "ada", "5.00", OrderStatus.CANCELLED))).isEmpty();
    }

    @Test
    void sorts_by_revenue_then_by_customer_id() {
        List<CustomerSummary> summaries = summarize(
                order("o1", "zed", "5.00", OrderStatus.PAID),
                order("o2", "amy", "5.00", OrderStatus.PAID),
                order("o3", "bob", "9.00", OrderStatus.PAID));

        assertThat(summaries).extracting(CustomerSummary::customerId).containsExactly("bob", "amy", "zed");
    }

    @Test
    void an_empty_source_gives_an_empty_report() {
        assertThat(summarize()).isEmpty();
    }
}
```
Two private helpers: `order(...)` builds an order from text, and `summarize(...)` runs the use case over an in-memory list; the lambda `() -> List.of(orders)` is a complete `OrderSource` because the interface has one method. Tests: totals per customer for paid and shipped orders (`containsExactly` checks both content and order); placed and cancelled orders are ignored; ties in revenue are broken by customer id (`extracting` picks one field of each element); an empty source gives an empty report.

#### `infrastructure/CsvOrderSourceIT.java` (integration test)

```java
package dev.plainround.orders.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import dev.plainround.orders.domain.InvalidOrderException;
import dev.plainround.orders.domain.Money;
import dev.plainround.orders.domain.Order;
import dev.plainround.orders.domain.OrderStatus;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Integration test: the adapter against real files. */
class CsvOrderSourceIT {

    @TempDir
    Path directory;

    private Path write(String content) throws IOException {
        return Files.writeString(directory.resolve("orders.csv"), content);
    }

    @Test
    void reads_orders_and_skips_blank_lines() throws IOException {
        Path file = write("id,customer,amount,status\no1,ada,10.50,paid\n\no2,grace,3,shipped\n");

        List<Order> orders = new CsvOrderSource(file).readAll();

        assertThat(orders).containsExactly(
                new Order("o1", "ada", Money.parse("10.50"), OrderStatus.PAID),
                new Order("o2", "grace", Money.parse("3"), OrderStatus.SHIPPED));
    }

    @Test
    void a_file_without_the_header_is_refused() throws IOException {
        Path file = write("o1,ada,10.50,paid\n");

        assertThatThrownBy(() -> new CsvOrderSource(file).readAll())
                .isInstanceOf(InvalidOrderException.class).hasMessageContaining("expected the header");
    }

    @Test
    void a_bad_line_is_reported_with_its_line_number() throws IOException {
        Path file = write("id,customer,amount,status\no1,ada,ten,paid\n");

        assertThatThrownBy(() -> new CsvOrderSource(file).readAll())
                .isInstanceOf(InvalidOrderException.class).hasMessageStartingWith("line 2:").hasMessageContaining("'ten'");
    }

    @Test
    void a_line_with_the_wrong_number_of_fields_is_reported() throws IOException {
        Path file = write("id,customer,amount,status\no1,ada,10\n");

        assertThatThrownBy(() -> new CsvOrderSource(file).readAll())
                .isInstanceOf(InvalidOrderException.class).hasMessageContaining("expected 4 fields, found 3");
    }

    @Test
    void a_missing_file_is_an_unchecked_io_error() {
        assertThatThrownBy(() -> new CsvOrderSource(directory.resolve("missing.csv")).readAll())
                .isInstanceOf(UncheckedIOException.class);
    }
}
```
The name ends in `IT`, so Failsafe runs it, not Surefire. `@TempDir` makes JUnit create a temporary folder for each test and delete it afterwards. The helper `write` saves text to `orders.csv`. Tests: valid rows are read and a blank line is skipped; a file without the header is refused; a bad amount reports `line 2:` and the text `'ten'`; a line with three fields reports "expected 4 fields, found 3"; a missing file gives `UncheckedIOException`.

#### `interfaces/MainIT.java` (integration test)

```java
package dev.plainround.orders.interfaces;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Integration test: the command line over a real file, end to end. */
class MainIT {

    @TempDir
    Path directory;

    private record Result(int status, String out, String err) {
    }

    private Result run(String... args) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        ByteArrayOutputStream err = new ByteArrayOutputStream();
        int status = Main.run(args, new PrintStream(out, true, StandardCharsets.UTF_8), new PrintStream(err, true, StandardCharsets.UTF_8));
        return new Result(status, out.toString(StandardCharsets.UTF_8), err.toString(StandardCharsets.UTF_8));
    }

    @Test
    void prints_a_report_for_a_valid_file() throws IOException {
        Path file = Files.writeString(directory.resolve("orders.csv"),
                "id,customer,amount,status\no1,ada,10.00,paid\no2,ada,5.50,shipped\no3,grace,3.00,paid\no4,bob,99.00,cancelled\n");

        Result result = run(file.toString());

        assertThat(result.status()).isZero();
        assertThat(result.out().lines().toList()).hasSize(3).satisfies(lines -> {
            assertThat(lines.get(0)).startsWith("ada").contains("2 orders").endsWith("15.50");
            assertThat(lines.get(1)).startsWith("grace").endsWith("3.00");
            assertThat(lines.get(2)).startsWith("TOTAL").contains("3 orders").endsWith("18.50");
        });
    }

    @Test
    void exits_2_and_says_why_for_bad_input() throws IOException {
        Path file = Files.writeString(directory.resolve("orders.csv"), "id,customer,amount,status\no1,ada,oops,paid\n");

        Result result = run(file.toString());

        assertThat(result.status()).isEqualTo(2);
        assertThat(result.err()).contains("error: line 2:");
        assertThat(result.out()).isEmpty();
    }

    @Test
    void exits_2_with_usage_when_the_argument_is_missing() {
        Result result = run();

        assertThat(result.status()).isEqualTo(2);
        assertThat(result.err()).contains("usage: order-summary");
    }

    @Test
    void exits_2_for_a_file_that_does_not_exist() {
        assertThat(run(directory.resolve("nope.csv").toString()).status()).isEqualTo(2);
    }
}
```
The private record `Result` holds status and both outputs. `run` calls `Main.run` with in-memory `ByteArrayOutputStream`s wrapped as `PrintStream`s instead of the real console. Tests: a valid file prints three lines (ada with 2 orders and 15.50, grace with 3.00, TOTAL with 3 orders and 18.50 — the cancelled order is excluded) and exits 0; bad input exits 2 with `error: line 2:` on the error stream and nothing on the output; a missing argument prints the usage and exits 2; a file that does not exist exits 2.
<!-- full-walkthrough:end -->

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
