package dev.plainround.orders.application;

import dev.plainround.orders.domain.Order;
import java.util.List;

/** Where orders come from. The use case asks for this port; infrastructure implements it. */
public interface OrderSource {

    /**
     * Reads every order.
     *
     * @return the orders, in the order the source holds them
     */
    List<Order> readAll();
}
