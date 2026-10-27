package dev.plainround.orders.domain;

/** A value that cannot be an order, an amount or a status. */
public final class InvalidOrderException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    /**
     * Creates the exception.
     *
     * @param message what was wrong, with the offending value
     */
    public InvalidOrderException(String message) {
        super(message);
    }
}
