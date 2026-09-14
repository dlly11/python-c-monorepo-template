#include "CppUTest/TestHarness.h"

#include "example/package_b.h"
#include "example/package_b_version.h"

TEST_GROUP(PackageBFarewell){};

TEST(PackageBFarewell, CreatesFarewell) {
    char output[64] = {0};

    LONGS_EQUAL(EXAMPLE_STATUS_OK, example_package_b_farewell("Ada", output, sizeof(output)));
    STRCMP_EQUAL("Goodbye, Ada!", output);
}

TEST_GROUP(PackageBVersion){};

TEST(PackageBVersion, MatchesRepositoryVersion) {
    STRCMP_EQUAL(EXAMPLE_EXPECTED_VERSION, EXAMPLE_PACKAGE_B_VERSION);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_MAJOR, EXAMPLE_PACKAGE_B_VERSION_MAJOR);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_MINOR, EXAMPLE_PACKAGE_B_VERSION_MINOR);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_PATCH, EXAMPLE_PACKAGE_B_VERSION_PATCH);
}
