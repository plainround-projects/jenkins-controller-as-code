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
