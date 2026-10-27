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
