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
