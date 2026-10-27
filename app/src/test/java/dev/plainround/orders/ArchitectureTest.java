package dev.plainround.orders;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

/** The dependency rule: domain depends on nothing; application on domain; nothing depends on interfaces. */
@AnalyzeClasses(packages = "dev.plainround.orders", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    @ArchTest
    static final ArchRule DOMAIN_DEPENDS_ON_NOTHING_ELSE_IN_THE_PROJECT = noClasses().that()
            .resideInAPackage("..domain..").should().dependOnClassesThat()
            .resideInAnyPackage("..application..", "..infrastructure..", "..interfaces..");

    @ArchTest
    static final ArchRule APPLICATION_DOES_NOT_KNOW_INFRASTRUCTURE_OR_INTERFACES = noClasses().that()
            .resideInAPackage("..application..").should().dependOnClassesThat()
            .resideInAnyPackage("..infrastructure..", "..interfaces..");

    @ArchTest
    static final ArchRule NOTHING_DEPENDS_ON_INTERFACES = noClasses().that()
            .resideOutsideOfPackage("..interfaces..").should().dependOnClassesThat()
            .resideInAPackage("..interfaces..");

    @ArchTest
    static final ArchRule INFRASTRUCTURE_DOES_NOT_DEPEND_ON_INTERFACES = noClasses().that()
            .resideInAPackage("..infrastructure..").should().dependOnClassesThat()
            .resideInAPackage("..interfaces..");
}
