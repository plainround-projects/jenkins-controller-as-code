package dev.plainround.orders;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/**
 * A switch for the pipeline's own demonstration: with {@code BREAK_A_TEST=true} in the environment this test fails,
 * which shows how Jenkins reports a failing test (the report is published, the build goes red, nothing is archived).
 */
class PipelineSwitchTest {

    @Test
    void the_pipeline_did_not_ask_for_a_failing_test() {
        assertThat(System.getenv("BREAK_A_TEST")).as("BREAK_A_TEST was set to true by the pipeline's parameter").isNotEqualTo("true");
    }
}
