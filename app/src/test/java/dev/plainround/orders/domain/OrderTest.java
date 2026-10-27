package dev.plainround.orders.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class OrderTest {

    @Test
    void an_order_needs_an_id_and_a_customer() {
        assertThatThrownBy(() -> new Order(" ", "c1", Money.ZERO, OrderStatus.PAID))
                .isInstanceOf(InvalidOrderException.class).hasMessageContaining("needs an id");
        assertThatThrownBy(() -> new Order("o1", "", Money.ZERO, OrderStatus.PAID))
                .isInstanceOf(InvalidOrderException.class).hasMessageContaining("needs a customer");
    }

    @Test
    void an_order_needs_a_total_and_a_status() {
        assertThatThrownBy(() -> new Order("o1", "c1", null, OrderStatus.PAID)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new Order("o1", "c1", Money.ZERO, null)).isInstanceOf(NullPointerException.class);
    }

    @ParameterizedTest
    @CsvSource({"paid,true", "SHIPPED,true", " Placed ,false", "cancelled,false"})
    void only_paid_and_shipped_orders_count_as_revenue(String text, boolean counts) {
        assertThat(OrderStatus.parse(text).countsAsRevenue()).isEqualTo(counts);
    }

    @Test
    void an_unknown_status_is_named() {
        assertThatThrownBy(() -> OrderStatus.parse("lost")).isInstanceOf(InvalidOrderException.class).hasMessageContaining("'lost'");
    }
}
