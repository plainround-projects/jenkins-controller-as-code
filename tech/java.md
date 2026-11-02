# Java 21

## 1. What it is

Java is a compiled, statically typed language that runs on the Java Virtual Machine (JVM). You write `.java` files; `javac` turns them into `.class` files; the JVM runs them. This repository uses Java 21 (the version is set by `maven.compiler.release`).

## 2. Why this repository uses it

The pipeline needs something real to build and test. `order-summary` is a small command-line program that reads a CSV of orders and prints revenue per customer. It is written in layers (domain, application, infrastructure, interfaces) and typed carefully, so the lesson's tests and rules have something to check.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `app/src/main/java/dev/plainround/orders/domain/` | `Money`, `Order`, `OrderStatus`, `CustomerSummary`, `InvalidOrderException` |
| `app/src/main/java/dev/plainround/orders/application/` | `OrderSource` (an interface) and `SummarizeOrders` (the use case) |
| `app/src/main/java/dev/plainround/orders/infrastructure/CsvOrderSource.java` | reads the CSV |
| `app/src/main/java/dev/plainround/orders/interfaces/` | `Main` (command line) and `ReportFormatter` |
| `app/src/test/java/` | tests (see the JUnit note) |

## 4. How it works underneath

- A **package** (`dev.plainround.orders.domain`) is a folder of classes; the first line `package ...;` must match the folder. `import` brings in classes from other packages.
- A **class** has fields and methods; `final` means it cannot be extended; `private` hides a member.
- A **record** (Java 16+) is a short way to write an immutable data class: `record Money(long cents)` generates the constructor, accessors (`cents()`), `equals`, `hashCode` and `toString`. A *compact constructor* (`public Money { ... }`) runs validation.
- An **enum** is a fixed set of named constants (`PLACED, PAID, SHIPPED, CANCELLED`) that can have methods.
- An **interface** is a contract of methods without implementation (`OrderSource.readAll()`).
- **Generics** (`List<Order>`, `Map<String, Money>`) say what a collection holds.
- **Exceptions**: `RuntimeException` subclasses are unchecked (not declared). `throw` raises one; `try/catch` handles it. `UncheckedIOException` wraps an I/O error in an unchecked one.
- **Streams** (`list.stream().map(...).sorted(...).toList()`) process collections as a pipeline of steps. **Method references** such as `Money::plus` name a method as a function.
- `Math.addExact` throws `ArithmeticException` on overflow instead of silently wrapping.

## 5. Walkthrough of this repository's use

### Domain
```java
public record Money(long cents) implements Comparable<Money> {
    public static final Money ZERO = new Money(0);
    public Money {
        if (cents < 0) { throw new InvalidOrderException("an amount cannot be negative: " + cents); }
    }
```
An immutable amount in **cents** (a `long`, never a floating-point number, to avoid rounding errors). The compact constructor rejects negatives. `implements Comparable<Money>` lets amounts be sorted.

```java
public static Money parse(String text) {
    String trimmed = text.strip();
    if (!trimmed.matches("\\d+(\\.\\d{1,2})?")) { throw new InvalidOrderException("not an amount: '" + text + "'"); }
    String[] parts = trimmed.split("\\.");
    long whole = Long.parseLong(parts[0]);
    long fraction = parts.length == 1 ? 0 : Long.parseLong((parts[1] + "0").substring(0, 2));
    return new Money(Math.addExact(Math.multiplyExact(whole, 100L), fraction));
}
```
The regular expression `\d+(\.\d{1,2})?` (backslashes doubled in Java source) accepts digits with an optional dot and one or two decimals. `"12.5"` becomes whole `12`, fraction `"5" + "0"` cut to `"50"`, so `1250` cents. `multiplyExact`/`addExact` refuse to overflow. `plus` adds two amounts; `compareTo` uses `Long.compare`; `toString` prints `%d.%02d` (for example `15.50`).

```java
public record Order(String id, String customerId, Money total, OrderStatus status) {
    public Order {
        Objects.requireNonNull(total, "total");
        Objects.requireNonNull(status, "status");
        if (id == null || id.isBlank()) { throw new InvalidOrderException("an order needs an id"); }
        ...
```
An order validates itself: no null total or status, no blank id or customer. `OrderStatus.parse(text)` upper-cases (with `Locale.ROOT`, so the result does not depend on the machine's language) and calls `valueOf`; an unknown name becomes an `InvalidOrderException`. `countsAsRevenue()` is true only for `PAID` and `SHIPPED`.

### Application
```java
public interface OrderSource { List<Order> readAll(); }
public final class SummarizeOrders {
    public List<CustomerSummary> run() {
        Map<String, Money> revenue = new TreeMap<>();
        Map<String, Integer> counts = new TreeMap<>();
        for (Order order : source.readAll()) {
            if (order.status().countsAsRevenue()) {
                revenue.merge(order.customerId(), order.total(), Money::plus);
                counts.merge(order.customerId(), 1, Integer::sum);
            }
        }
        return revenue.entrySet().stream()
                .map(entry -> new CustomerSummary(entry.getKey(), counts.get(entry.getKey()), entry.getValue()))
                .sorted(Comparator.comparing(CustomerSummary::revenue).reversed().thenComparing(CustomerSummary::customerId))
                .toList();
    }
}
```
The use case depends on the **interface**, not on CSV files (a *port*). `TreeMap` keeps customers sorted by id. `map.merge(key, value, function)` inserts the value or combines it with the existing one. The stream turns each entry into a `CustomerSummary`, sorts by revenue (largest first) and then by customer id, and returns an unmodifiable list.

### Infrastructure
`CsvOrderSource implements OrderSource` reads all lines with `Files.readAllLines(file, UTF_8)`, checks the header `id,customer,amount,status`, skips blank lines, splits each line with `line.split(",", -1)` (the `-1` keeps empty trailing fields), requires four fields and builds an `Order`; a bad line is reported with its **line number**. An `IOException` becomes an `UncheckedIOException`.

### Interfaces
`Main.run(args, out, err)` returns an exit code instead of calling `System.exit`, so tests can call it: `0` on success, `2` for bad usage or bad input. `main` is just `System.exit(run(args, System.out, System.err))`. `ReportFormatter.format` builds lines with `String.format("%-12s %3d orders %12s%n", ...)` (left-aligned name, right-aligned count and amount, platform newline).

### Compiler strictness
The POM compiles with `-Xlint:all -Werror`: **every compiler warning is an error**. That is why `InvalidOrderException` declares `serialVersionUID`.



<!-- full-walkthrough:begin -->
### 5.A Full walkthrough: every production Java file

**Java in five sentences.** Java source is text in `.java` files compiled to bytecode that the Java Virtual Machine (JVM) runs. Code lives in **classes**; a class belongs to a **package** (a folder-like namespace written `dev.plainround.orders.domain`) declared on the first line and `import` lines bring in classes from other packages. A **record** is a short way to write an immutable data class: the list in parentheses declares fields, and Java generates the constructor, accessor methods (`customerId()`), `equals`, `hashCode` and `toString`. An **interface** lists methods without bodies; a class that `implements` it must provide them. Text between `/** ... */` is a *Javadoc* comment that documents the following item, and Checkstyle requires one on every public type.

**Architecture.** The packages follow the *dependency rule* tested by `ArchitectureTest`: `domain` (the core concepts) depends on nothing in the project; `application` (the use case) depends only on `domain`; `infrastructure` (CSV reading) and `interfaces` (the command line) sit on the outside and depend inward. The use case asks for an `OrderSource` *port* (an interface it owns), and `CsvOrderSource` is an *adapter* that implements it.

#### `domain/InvalidOrderException.java`

```java
package dev.plainround.orders.domain;

/** A value that cannot be an order, an amount or a status. */
public final class InvalidOrderException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    /**
     * Creates the exception.
     *
     * @param message what was wrong, with the offending value
     */
    public InvalidOrderException(String message) {
        super(message);
    }
}
```
An **exception** is an object that signals an error. This one extends `RuntimeException`, so callers are not forced to declare it. `final` means no class can extend it. `serialVersionUID` is a version number needed for Java's object serialisation format (the compiler lint demands it). The constructor passes the message to the parent class with `super(message)`.

#### `domain/Money.java`

```java
package dev.plainround.orders.domain;

/**
 * An amount of money in whole cents. Immutable; negative amounts are rejected.
 *
 * @param cents the amount in the smallest currency unit
 */
public record Money(long cents) implements Comparable<Money> {

    /** The zero amount. */
    public static final Money ZERO = new Money(0);

    /**
     * Creates an amount.
     *
     * @throws InvalidOrderException when {@code cents} is negative
     */
    public Money {
        if (cents < 0) {
            throw new InvalidOrderException("an amount cannot be negative: " + cents);
        }
    }

```
`Money` is a record with one field, `cents`, a `long` (64-bit whole number). Storing whole cents avoids the rounding errors of decimal fractions. `implements Comparable<Money>` allows amounts to be sorted. `ZERO` is a constant (`static final`). The **compact constructor** (`public Money { ... }`, with no parameter list) runs before the fields are set and here rejects a negative amount by throwing `InvalidOrderException`, so no invalid `Money` can exist.

```java
    /**
     * Parses a decimal amount such as {@code 12.50} or {@code 7}.
     *
     * @param text the amount with at most two decimals
     * @return the amount in cents
     * @throws InvalidOrderException when the text is not an amount
     */
    public static Money parse(String text) {
        String trimmed = text.strip();
        if (!trimmed.matches("\\d+(\\.\\d{1,2})?")) {
            throw new InvalidOrderException("not an amount: '" + text + "'");
        }
        String[] parts = trimmed.split("\\.");
        long whole = Long.parseLong(parts[0]);
        long fraction = parts.length == 1 ? 0 : Long.parseLong((parts[1] + "0").substring(0, 2));
        return new Money(Math.addExact(Math.multiplyExact(whole, 100L), fraction));
    }
```
`parse` turns text such as `12.50` into cents. `strip()` trims spaces; `matches("\\d+(\\.\\d{1,2})?")` tests against a regular expression meaning digits, optionally followed by a dot and one or two digits (the double backslash is how a single backslash is written in a Java string). `split("\\.")` cuts at the dot. `whole` is the part before the dot. For the fraction, `(parts[1] + "0").substring(0, 2)` pads one digit (`5` becomes `50`) and keeps two. `Math.multiplyExact` and `Math.addExact` do arithmetic but throw `ArithmeticException` on overflow instead of silently wrapping around.

```java
    /**
     * Adds two amounts.
     *
     * @param other the amount to add
     * @return the sum
     */
    public Money plus(Money other) {
        return new Money(Math.addExact(cents, other.cents));
    }

    @Override
    public int compareTo(Money other) {
        return Long.compare(cents, other.cents);
    }

    @Override
    public String toString() {
        return String.format("%d.%02d", cents / 100, cents % 100);
    }
}
```
`plus` adds two amounts with overflow protection. `compareTo` returns a negative, zero or positive number for ordering. `toString` formats with `%d.%02d`: whole units, a dot, and cents padded to two digits. `@Override` asks the compiler to check that the method really overrides one from a parent type.

#### `domain/OrderStatus.java`

```java
package dev.plainround.orders.domain;

import java.util.Locale;

/** Where an order is in its life. Only paid and shipped orders count towards a customer's total. */
public enum OrderStatus {
    /** Placed and not yet paid. */
    PLACED,
    /** Paid. */
    PAID,
    /** Shipped. */
    SHIPPED,
    /** Cancelled. */
    CANCELLED;

    /**
     * Reads a status from text, ignoring case and surrounding spaces.
     *
     * @param text the status name
     * @return the status
     * @throws InvalidOrderException when the name is unknown
     */
    public static OrderStatus parse(String text) {
        try {
            return valueOf(text.strip().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException unknown) {
            throw new InvalidOrderException("unknown status: '" + text + "'");
        }
    }

    /** Whether orders in this status are counted as revenue. */
    public boolean countsAsRevenue() {
        return this == PAID || this == SHIPPED;
    }
}
```
An **enum** is a type with a fixed set of values, here the four states of an order. `parse` converts text: `strip()` removes spaces, `toUpperCase(Locale.ROOT)` makes it upper-case in a language-independent way, and `valueOf` finds the matching constant or throws `IllegalArgumentException`, which is caught and turned into the project's own exception with the offending text. `countsAsRevenue` is true for `PAID` and `SHIPPED` (`this == PAID` compares enum constants by identity).

#### `domain/Order.java`

```java
package dev.plainround.orders.domain;

import java.util.Objects;

/**
 * One order.
 *
 * @param id the order id
 * @param customerId the customer who placed it
 * @param total the order total
 * @param status where the order is in its life
 */
public record Order(String id, String customerId, Money total, OrderStatus status) {

    /**
     * Creates an order.
     *
     * @throws InvalidOrderException when an id is blank
     */
    public Order {
        Objects.requireNonNull(total, "total");
        Objects.requireNonNull(status, "status");
        if (id == null || id.isBlank()) {
            throw new InvalidOrderException("an order needs an id");
        }
        if (customerId == null || customerId.isBlank()) {
            throw new InvalidOrderException("order " + id + " needs a customer");
        }
    }
}
```
An `Order` has an id, a customer id, a total and a status. The compact constructor first requires that `total` and `status` are not null (`Objects.requireNonNull` throws `NullPointerException` with the given name), then rejects a missing or blank id or customer with a clear message.

#### `domain/CustomerSummary.java`

```java
package dev.plainround.orders.domain;

/**
 * What one customer bought.
 *
 * @param customerId the customer
 * @param orders how many orders count as revenue
 * @param revenue the sum of those orders
 */
public record CustomerSummary(String customerId, int orders, Money revenue) {
}
```
The result of the use case for one customer: id, order count, revenue. The empty body `{ }` is allowed because a record needs nothing more.

#### `application/OrderSource.java`

```java
package dev.plainround.orders.application;

import dev.plainround.orders.domain.Order;
import java.util.List;

/** Where orders come from. The use case asks for this port; infrastructure implements it. */
public interface OrderSource {

    /**
     * Reads every order.
     *
     * @return the orders, in the order the source holds them
     */
    List<Order> readAll();
}
```
The *port*. `List<Order>` is a list whose elements are `Order`s (generics). Because the interface has exactly one method, a test can supply it as a one-line lambda.

#### `application/SummarizeOrders.java`

```java
package dev.plainround.orders.application;

import dev.plainround.orders.domain.CustomerSummary;
import dev.plainround.orders.domain.Money;
import dev.plainround.orders.domain.Order;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** The use case: total the revenue per customer, biggest first. */
public final class SummarizeOrders {
    private final OrderSource source;

    /**
     * Creates the use case.
     *
     * @param source where the orders come from
     */
    public SummarizeOrders(OrderSource source) {
        this.source = source;
    }
```
The class is `final` and keeps the source in a `private final` field assigned in the constructor.

```java
    /**
     * Totals paid and shipped orders per customer.
     *
     * @return one summary per customer with revenue, ordered by revenue then customer id
     */
    public List<CustomerSummary> run() {
        Map<String, Money> revenue = new TreeMap<>();
        Map<String, Integer> counts = new TreeMap<>();
        for (Order order : source.readAll()) {
            if (order.status().countsAsRevenue()) {
                revenue.merge(order.customerId(), order.total(), Money::plus);
                counts.merge(order.customerId(), 1, Integer::sum);
            }
        }
        return revenue.entrySet().stream()
                .map(entry -> new CustomerSummary(entry.getKey(), counts.get(entry.getKey()), entry.getValue()))
                .sorted(Comparator.comparing(CustomerSummary::revenue).reversed()
                        .thenComparing(CustomerSummary::customerId))
                .toList();
    }
}
```
`run` creates two `TreeMap`s (maps kept sorted by key): revenue and count per customer. For each order that `countsAsRevenue`, `merge(key, value, function)` inserts the value if the key is new or combines the old and new with the function: `Money::plus` (a *method reference*, shorthand for a function that calls `plus`) and `Integer::sum`. Then a **stream** pipeline processes the entries: `map` turns each into a `CustomerSummary`, `sorted` orders them by revenue (`Comparator.comparing(...).reversed()` for biggest first) then by customer id to break ties, and `toList()` collects the result into a list that cannot be modified.

#### `infrastructure/CsvOrderSource.java`

```java
package dev.plainround.orders.infrastructure;

import dev.plainround.orders.application.OrderSource;
import dev.plainround.orders.domain.InvalidOrderException;
import dev.plainround.orders.domain.Money;
import dev.plainround.orders.domain.Order;
import dev.plainround.orders.domain.OrderStatus;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Reads orders from a CSV file with the header {@code id,customer,amount,status}. */
public final class CsvOrderSource implements OrderSource {
    private static final String HEADER = "id,customer,amount,status";
    private final Path file;

    /**
     * Creates a source over a file.
     *
     * @param file the CSV file
     */
    public CsvOrderSource(Path file) {
        this.file = file;
    }

```
The imports bring in file reading classes. `HEADER` is the exact first line expected in the file. The class `implements OrderSource` and stores the file path.

```java
    @Override
    public List<Order> readAll() {
        List<String> lines;
        try {
            lines = Files.readAllLines(file, StandardCharsets.UTF_8);
        } catch (IOException failure) {
            throw new UncheckedIOException("cannot read " + file, failure);
        }
        if (lines.isEmpty() || !lines.get(0).strip().equals(HEADER)) {
            throw new InvalidOrderException("expected the header '" + HEADER + "' in " + file);
        }
        List<Order> orders = new ArrayList<>();
        for (int index = 1; index < lines.size(); index++) {
            String line = lines.get(index);
            if (!line.isBlank()) {
                orders.add(parse(line, index + 1));
            }
        }
        return orders;
    }
```
`readAll` reads all lines as UTF-8. A failure to read (`IOException`, a *checked* exception that must be handled) is wrapped in `UncheckedIOException` with the file name. It then requires the first line (after `strip()`) to equal the header, else throws. It loops from index 1 (skipping the header), ignores blank lines and parses each line, passing `index + 1` so error messages use human line numbers (starting at 1).

```java
    private static Order parse(String line, int lineNumber) {
        String[] fields = line.split(",", -1);
        if (fields.length != 4) {
            throw new InvalidOrderException("line " + lineNumber + ": expected 4 fields, found " + fields.length);
        }
        try {
            return new Order(fields[0].strip(), fields[1].strip(), Money.parse(fields[2]), OrderStatus.parse(fields[3]));
        } catch (InvalidOrderException problem) {
            throw new InvalidOrderException("line " + lineNumber + ": " + problem.getMessage());
        }
    }
}
```
`parse` splits at commas; the `-1` limit keeps empty trailing fields so a line with missing values is counted correctly. It insists on exactly four fields, and builds an `Order` from the trimmed fields; any `InvalidOrderException` from the pieces is rethrown with the line number in front.

#### `interfaces/ReportFormatter.java`

```java
package dev.plainround.orders.interfaces;

import dev.plainround.orders.domain.CustomerSummary;
import dev.plainround.orders.domain.Money;
import java.util.List;

/** Turns summaries into the lines the command prints. */
final class ReportFormatter {
    private ReportFormatter() {
    }

    /**
     * Formats a report.
     *
     * @param summaries the summaries, already ordered
     * @return one line per customer, then a total line
     */
    static String format(List<CustomerSummary> summaries) {
        StringBuilder report = new StringBuilder();
        long total = 0;
        for (CustomerSummary summary : summaries) {
            report.append(String.format("%-12s %3d orders %12s%n", summary.customerId(), summary.orders(), summary.revenue()));
            total += summary.revenue().cents();
        }
        report.append(String.format("%-12s %3d orders %12s%n", "TOTAL",
                summaries.stream().mapToInt(CustomerSummary::orders).sum(),
                new Money(total)));
        return report.toString();
    }
}
```
The class is package-private (no `public`) and has a private constructor so nobody can create instances; it only holds one static method. `String.format` uses a template: `%-12s` a string left-aligned in 12 characters, `%3d` a whole number in 3 characters, `%12s` right-aligned, `%n` a line break for the platform. It adds one line per customer, accumulates the cents in `total`, then adds a `TOTAL` line with `mapToInt(...).sum()` for the order count. `StringBuilder` builds text efficiently.

#### `interfaces/Main.java`

```java
package dev.plainround.orders.interfaces;

import dev.plainround.orders.application.SummarizeOrders;
import dev.plainround.orders.domain.InvalidOrderException;
import dev.plainround.orders.infrastructure.CsvOrderSource;
import java.io.PrintStream;
import java.io.UncheckedIOException;
import java.nio.file.Path;

/** The command line: {@code java -jar order-summary.jar orders.csv}. */
public final class Main {
    private Main() {
    }

    /**
     * Runs the command and exits with its status.
     *
     * @param args the path of the orders CSV
     */
    public static void main(String[] args) {
        System.exit(run(args, System.out, System.err));
    }

    /**
     * Runs the command without exiting, so tests can call it.
     *
     * @param args the path of the orders CSV
     * @param out where the report goes
     * @param err where problems go
     * @return 0 on success, 2 for bad usage or bad input
     */
    static int run(String[] args, PrintStream out, PrintStream err) {
        if (args.length != 1) {
            err.println("usage: order-summary <orders.csv>");
            return 2;
        }
        try {
            out.print(ReportFormatter.format(new SummarizeOrders(new CsvOrderSource(Path.of(args[0]))).run()));
            return 0;
        } catch (InvalidOrderException | UncheckedIOException problem) {
            err.println("error: " + problem.getMessage());
            return 2;
        }
    }
}
```
`main(String[] args)` is where the JVM starts a program; it calls `run` and passes the result to `System.exit`, which ends the process with that exit code. `run` is separate and takes the output streams as parameters, so tests can capture them. With any argument count other than 1 it prints usage to the error stream and returns 2. Otherwise it wires the objects together (`new SummarizeOrders(new CsvOrderSource(Path.of(args[0])))`), prints the formatted report and returns 0. `catch (InvalidOrderException | UncheckedIOException problem)` handles either of two exception types in one block, prints `error: ...` and returns 2.
<!-- full-walkthrough:end -->

## 6. Try it yourself

1. `cd app && ./mvnw --batch-mode --no-transfer-progress -q package -DskipTests && java -jar target/order-summary-1.0.0.jar src/test/resources/orders-sample.csv` : a report line per customer and a `TOTAL` line.
2. `java -jar target/order-summary-1.0.0.jar; echo $?` : `usage: order-summary <orders.csv>` and `2`.
3. `printf 'id,customer,amount,status\no1,ada,oops,paid\n' > /tmp/bad.csv; java -jar target/order-summary-1.0.0.jar /tmp/bad.csv; echo $?` : `error: line 2: not an amount: 'oops'` and `2`.
4. `java -version` : 21.
5. `jshell` then `new java.math.BigDecimal("0.1").add(new java.math.BigDecimal("0.2"))` : exact decimal arithmetic, the reason money is in whole cents here.

## 7. Mistakes people make

- Using `double` for money (0.1 + 0.2 is not 0.3). Cents in a `long` avoid it.
- Catching `Exception` broadly and hiding bugs. Only the expected exceptions are caught in `Main`.
- `String.toUpperCase()` without a locale, which behaves differently in Turkish. `Locale.ROOT` fixes it.
- Mutable state in domain objects. Records are immutable.

## 8. Check yourself

1. What does a record generate?
   *Answer:* A constructor, accessors, `equals`, `hashCode` and `toString`.
2. Why is money stored in cents as a `long`?
   *Answer:* To avoid floating-point rounding errors.
3. What does `Math.addExact` do on overflow?
   *Answer:* Throws `ArithmeticException` instead of wrapping around.
4. Why does `Main.run` return an int?
   *Answer:* So tests can call it without ending the JVM.
5. What does `-Werror` change?
   *Answer:* Compiler warnings fail the build.

## 9. Further reading

- Java SE 21 documentation: <https://docs.oracle.com/en/java/javase/21/>. Language guide for records: <https://docs.oracle.com/en/java/javase/21/language/records.html>.
