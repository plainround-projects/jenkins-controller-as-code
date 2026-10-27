package dev.plainround.orders.application;

import dev.plainround.orders.domain.CustomerSummary;
import dev.plainround.orders.domain.Money;
import dev.plainround.orders.domain.Order;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** The use case: total the revenue per customer, biggest first. */
public final class SummarizeOrders {
    private final OrderSource source;

    /**
     * Creates the use case.
     *
     * @param source where the orders come from
     */
    public SummarizeOrders(OrderSource source) {
        this.source = source;
    }

    /**
     * Totals paid and shipped orders per customer.
     *
     * @return one summary per customer with revenue, ordered by revenue then customer id
     */
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
                .sorted(Comparator.comparing(CustomerSummary::revenue).reversed()
                        .thenComparing(CustomerSummary::customerId))
                .toList();
    }
}
