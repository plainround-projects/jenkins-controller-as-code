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
