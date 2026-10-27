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
