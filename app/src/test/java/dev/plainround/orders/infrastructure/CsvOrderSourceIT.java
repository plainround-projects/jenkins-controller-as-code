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
