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
