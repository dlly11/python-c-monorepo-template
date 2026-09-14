#include "example/core.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(expression)                                                                          \
    do {                                                                                           \
        if (!(expression)) {                                                                       \
            (void)fprintf(stderr, "check failed at %s:%d: %s\n", __FILE__, __LINE__, #expression); \
            return EXIT_FAILURE;                                                                   \
        }                                                                                          \
    } while (0)

int main(void) {
    char output[64] = {0};
    char small_output[4] = {0};
    const example_status unknown_status =
        (example_status)99; // NOLINT(clang-analyzer-optin.core.EnumCastOutOfRange)

    CHECK(example_core_format_message("Hello", "Ada", output, sizeof(output)) == EXAMPLE_STATUS_OK);
    CHECK(strcmp(output, "Hello, Ada!") == 0);
    CHECK(example_core_format_message("Hello", "Ada", small_output, sizeof(small_output)) ==
          EXAMPLE_STATUS_BUFFER_TOO_SMALL);
    CHECK(example_core_format_message(NULL, "Ada", output, sizeof(output)) ==
          EXAMPLE_STATUS_INVALID_ARGUMENT);
    CHECK(example_core_format_message("Hello", NULL, output, sizeof(output)) ==
          EXAMPLE_STATUS_INVALID_ARGUMENT);
    CHECK(example_core_format_message("Hello", "Ada", NULL, sizeof(output)) ==
          EXAMPLE_STATUS_INVALID_ARGUMENT);
    CHECK(example_core_format_message("Hello", "Ada", output, 0U) ==
          EXAMPLE_STATUS_INVALID_ARGUMENT);
    CHECK(example_core_format_message("", "Ada", output, sizeof(output)) ==
          EXAMPLE_STATUS_INVALID_ARGUMENT);
    CHECK(example_core_format_message("Hello", "", output, sizeof(output)) ==
          EXAMPLE_STATUS_INVALID_ARGUMENT);
    CHECK(strcmp(example_core_status_string(EXAMPLE_STATUS_OK), "ok") == 0);
    CHECK(strcmp(example_core_status_string(EXAMPLE_STATUS_INVALID_ARGUMENT), "invalid argument") ==
          0);
    CHECK(strcmp(example_core_status_string(EXAMPLE_STATUS_BUFFER_TOO_SMALL), "buffer too small") ==
          0);
    CHECK(strcmp(example_core_status_string(EXAMPLE_STATUS_FORMAT_ERROR), "format error") == 0);
    CHECK(strcmp(example_core_status_string(unknown_status), "unknown status") == 0);

    return EXIT_SUCCESS;
}
