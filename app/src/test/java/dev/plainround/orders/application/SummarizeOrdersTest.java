package dev.plainround.orders.application;

import static org.assertj.core.api.Assertions.assertThat;

import dev.plainround.orders.domain.CustomerSummary;
import dev.plainround.orders.domain.Money;
import dev.plainround.orders.domain.Order;
import dev.plainround.orders.domain.OrderStatus;
import java.util.List;
import org.junit.jupiter.api.Test;

class SummarizeOrdersTest {

    private static Order order(String id, String customer, String amount, OrderStatus status) {
        return new Order(id, customer, Money.parse(amount), status);
    }

    private static List<CustomerSummary> summarize(Order... orders) {
        return new SummarizeOrders(() -> List.of(orders)).run();
    }

    @Test
    void totals_paid_and_shipped_orders_per_customer() {
        List<CustomerSummary> summaries = summarize(
                order("o1", "ada", "10.00", OrderStatus.PAID),
                order("o2", "ada", "5.50", OrderStatus.SHIPPED),
                order("o3", "grace", "3.00", OrderStatus.PAID));

        assertThat(summaries).containsExactly(
                new CustomerSummary("ada", 2, Money.parse("15.50")),
                new CustomerSummary("grace", 1, Money.parse("3.00")));
    }

    @Test
    void ignores_placed_and_cancelled_orders() {
        assertThat(summarize(
                order("o1", "ada", "10.00", OrderStatus.PLACED),
                order("o2", "ada", "5.00", OrderStatus.CANCELLED))).isEmpty();
    }

    @Test
    void sorts_by_revenue_then_by_customer_id() {
        List<CustomerSummary> summaries = summarize(
                order("o1", "zed", "5.00", OrderStatus.PAID),
                order("o2", "amy", "5.00", OrderStatus.PAID),
                order("o3", "bob", "9.00", OrderStatus.PAID));

        assertThat(summaries).extracting(CustomerSummary::customerId).containsExactly("bob", "amy", "zed");
    }

    @Test
    void an_empty_source_gives_an_empty_report() {
        assertThat(summarize()).isEmpty();
    }
}
