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
