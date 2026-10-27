# CSV

## 1. What it is

CSV ("comma-separated values") is a text format for tables: one row per line, fields separated by commas, usually with a header line naming the columns.

## 2. Why this repository uses it

The Java program reads orders from a CSV file. The format is deliberately simple so the code's validation (header, field count, amounts, statuses) is the interesting part.

## 3. Where it appears

| File | What it does with this technology |
| --- | --- |
| `app/src/test/resources/orders-sample.csv` | the sample data the end-to-end run uses |
| `app/src/main/java/.../infrastructure/CsvOrderSource.java` | the reader |
| `app/src/test/java/.../CsvOrderSourceIT.java, MainIT.java` | files written on the fly in tests |

## 4. How it works underneath

- The first line must be exactly `id,customer,amount,status` here.
- Each following line has four fields; blank lines are skipped.
- This reader does **no quoting**: a comma inside a field would split it. That is a stated limit of this small program, not a general CSV parser.
- Line numbers in error messages count from 1 and include the header, so the first data line is line 2.

## 5. Walkthrough of this repository's use

```
id,customer,amount,status
o-1001,ada,120.00,paid
o-1002,grace,35.50,shipped
o-1003,ada,18.25,shipped
o-1004,linus,60.00,placed
```
`CsvOrderSource.readAll()` reads all lines as UTF-8, checks the first against the header, then for each non-blank line calls `line.split(",", -1)` (`-1` keeps empty trailing fields so `o1,ada,10,` is four fields, not three) and requires exactly four. It builds `new Order(id, customer, Money.parse(amount), OrderStatus.parse(status))`; text is trimmed and the status is case-insensitive. Any `InvalidOrderException` is rethrown with `"line N: ..."` in front, so a user sees which line is wrong. Only `paid` and `shipped` orders count toward revenue, so `linus` (placed) does not appear in the report.

## 6. Try it yourself

1. `cat app/src/test/resources/orders-sample.csv` : the sample.
2. `java -jar app/target/order-summary-1.0.0.jar app/src/test/resources/orders-sample.csv` : `ada ... 138.25` and `grace ... 35.50`, then `TOTAL`.
3. Remove the header line from a copy and run the program : `error: expected the header 'id,customer,amount,status' in <file>` and exit code 2.
4. Change an amount to `12,5` : `error: line 2: expected 4 fields, found 5`.
5. `awk -F, 'NR>1 && ($4=="paid"||$4=="shipped"){s[$2]+=$3} END{for(c in s) print c, s[c]}' app/src/test/resources/orders-sample.csv` : the same totals computed by awk.

## 7. Mistakes people make

- Assuming CSV means 'comma-split is enough'. Real CSV allows quoted fields; this program does not.
- Reading amounts as floating-point numbers.
- Forgetting that the header is line 1 when reporting errors.

## 8. Check yourself

1. What must the first line of the file be?
   *Answer:* `id,customer,amount,status`.
2. Why `split(",", -1)`?
   *Answer:* To keep empty trailing fields.
3. Which orders count as revenue?
   *Answer:* Only `paid` and `shipped`.
4. What is the line number of the first data line in an error message?
   *Answer:* 2.
5. What does this reader not support?
   *Answer:* Quoted fields containing commas.

## 9. Further reading

- RFC 4180 (the common CSV description): <https://www.rfc-editor.org/rfc/rfc4180>.
