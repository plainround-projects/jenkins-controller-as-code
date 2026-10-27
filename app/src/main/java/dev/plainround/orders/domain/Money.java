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
