package dev.plainround.orders.interfaces;

import dev.plainround.orders.domain.CustomerSummary;
import dev.plainround.orders.domain.Money;
import java.util.List;

/** Turns summaries into the lines the command prints. */
final class ReportFormatter {
    private ReportFormatter() {
    }

    /**
     * Formats a report.
     *
     * @param summaries the summaries, already ordered
     * @return one line per customer, then a total line
     */
    static String format(List<CustomerSummary> summaries) {
        StringBuilder report = new StringBuilder();
        long total = 0;
        for (CustomerSummary summary : summaries) {
            report.append(String.format("%-12s %3d orders %12s%n", summary.customerId(), summary.orders(), summary.revenue()));
            total += summary.revenue().cents();
        }
        report.append(String.format("%-12s %3d orders %12s%n", "TOTAL",
                summaries.stream().mapToInt(CustomerSummary::orders).sum(),
                new Money(total)));
        return report.toString();
    }
}
