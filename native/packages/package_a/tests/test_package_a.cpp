#include "CppUTest/TestHarness.h"

#include "example/package_a.h"
#include "example/package_a_version.h"

TEST_GROUP(PackageAGreeting){};

TEST(PackageAGreeting, CreatesGreeting) {
    char output[64] = {0};

    LONGS_EQUAL(EXAMPLE_STATUS_OK, example_package_a_greeting("Ada", output, sizeof(output)));
    STRCMP_EQUAL("Hello, Ada!", output);
}

TEST_GROUP(PackageAVersion){};

TEST(PackageAVersion, MatchesRepositoryVersion) {
    STRCMP_EQUAL(EXAMPLE_EXPECTED_VERSION, EXAMPLE_PACKAGE_A_VERSION);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_MAJOR, EXAMPLE_PACKAGE_A_VERSION_MAJOR);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_MINOR, EXAMPLE_PACKAGE_A_VERSION_MINOR);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_PATCH, EXAMPLE_PACKAGE_A_VERSION_PATCH);
}
