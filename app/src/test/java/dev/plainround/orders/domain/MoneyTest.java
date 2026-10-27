package dev.plainround.orders.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

class MoneyTest {

    @ParameterizedTest
    @CsvSource({"0,0", "7,700", "12.5,1250", "12.50,1250", "0.07,7", "1000000.99,100000099"})
    void parses_decimal_amounts_into_cents(String text, long cents) {
        assertThat(Money.parse(text).cents()).isEqualTo(cents);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "abc", "-1", "1.234", "1,5", "1.", ".5"})
    void rejects_text_that_is_not_an_amount(String text) {
        assertThatThrownBy(() -> Money.parse(text)).isInstanceOf(InvalidOrderException.class).hasMessageContaining("not an amount");
    }

    @Test
    void rejects_a_negative_amount() {
        assertThatThrownBy(() -> new Money(-1)).isInstanceOf(InvalidOrderException.class);
    }

    @Test
    void adds_amounts_and_prints_them_with_two_decimals() {
        assertThat(Money.parse("1.05").plus(Money.parse("2.10"))).hasToString("3.15");
        assertThat(Money.ZERO).hasToString("0.00");
    }

    @Test
    void orders_by_amount() {
        assertThat(Money.parse("2")).isGreaterThan(Money.parse("1.99"));
    }

    @Test
    void refuses_to_overflow() {
        assertThatThrownBy(() -> new Money(Long.MAX_VALUE).plus(new Money(1))).isInstanceOf(ArithmeticException.class);
    }
}
