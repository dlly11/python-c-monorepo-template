#include "CppUTest/TestHarness.h"

#include "example/core.h"
#include "example/core_version.h"

extern "C" const char *example_test_unknown_status_string(void);

TEST_GROUP(CoreFormatMessage){};

TEST(CoreFormatMessage, FormatsMessage) {
    char output[64] = {0};

    LONGS_EQUAL(EXAMPLE_STATUS_OK,
                example_core_format_message("Hello", "Ada", output, sizeof(output)));
    STRCMP_EQUAL("Hello, Ada!", output);
}

TEST(CoreFormatMessage, ReportsSmallOutputBuffer) {
    char output[4] = {0};

    LONGS_EQUAL(EXAMPLE_STATUS_BUFFER_TOO_SMALL,
                example_core_format_message("Hello", "Ada", output, sizeof(output)));
}

TEST(CoreFormatMessage, AcceptsExactFit) {
    char output[sizeof("Hello, Ada!")] = {0};

    LONGS_EQUAL(EXAMPLE_STATUS_OK,
                example_core_format_message("Hello", "Ada", output, sizeof(output)));
    STRCMP_EQUAL("Hello, Ada!", output);
}

TEST(CoreFormatMessage, TerminatesOutputOneByteShort) {
    char output[sizeof("Hello, Ada!") - 1U] = {0};

    LONGS_EQUAL(EXAMPLE_STATUS_BUFFER_TOO_SMALL,
                example_core_format_message("Hello", "Ada", output, sizeof(output)));
    STRCMP_EQUAL("Hello, Ada", output);
}

TEST(CoreFormatMessage, TerminatesSingleByteOutput) {
    char output[1] = {'x'};

    LONGS_EQUAL(EXAMPLE_STATUS_BUFFER_TOO_SMALL,
                example_core_format_message("Hello", "Ada", output, sizeof(output)));
    STRCMP_EQUAL("", output);
}

TEST(CoreFormatMessage, LeavesOutputUntouchedAfterValidationFailure) {
    char output[] = "unchanged";

    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message("Hello", "", output, sizeof(output)));
    STRCMP_EQUAL("unchanged", output);
    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message("Hello", "Ada", output, 0U));
    STRCMP_EQUAL("unchanged", output);
}

TEST(CoreFormatMessage, RejectsInvalidArguments) {
    char output[64] = {0};

    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message(nullptr, "Ada", output, sizeof(output)));
    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message("Hello", nullptr, output, sizeof(output)));
    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message("Hello", "Ada", nullptr, sizeof(output)));
    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message("Hello", "Ada", output, 0U));
    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message("", "Ada", output, sizeof(output)));
    LONGS_EQUAL(EXAMPLE_STATUS_INVALID_ARGUMENT,
                example_core_format_message("Hello", "", output, sizeof(output)));
}

TEST_GROUP(CoreStatusString){};

TEST(CoreStatusString, DescribesEveryStatus) {
    STRCMP_EQUAL("ok", example_core_status_string(EXAMPLE_STATUS_OK));
    STRCMP_EQUAL("invalid argument", example_core_status_string(EXAMPLE_STATUS_INVALID_ARGUMENT));
    STRCMP_EQUAL("buffer too small", example_core_status_string(EXAMPLE_STATUS_BUFFER_TOO_SMALL));
    STRCMP_EQUAL("format error", example_core_status_string(EXAMPLE_STATUS_FORMAT_ERROR));
    STRCMP_EQUAL("unknown status", example_test_unknown_status_string());
}

TEST_GROUP(CoreVersion){};

TEST(CoreVersion, MatchesRepositoryVersion) {
    STRCMP_EQUAL(EXAMPLE_EXPECTED_VERSION, EXAMPLE_CORE_VERSION);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_MAJOR, EXAMPLE_CORE_VERSION_MAJOR);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_MINOR, EXAMPLE_CORE_VERSION_MINOR);
    LONGS_EQUAL(EXAMPLE_EXPECTED_VERSION_PATCH, EXAMPLE_CORE_VERSION_PATCH);
}
