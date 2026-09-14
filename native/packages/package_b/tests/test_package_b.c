#include "example/package_b.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    char output[64] = {0};
    const example_status status = example_package_b_farewell("Ada", output, sizeof(output));

    if (status != EXAMPLE_STATUS_OK) {
        (void)fprintf(stderr, "unexpected status: %s\n", example_core_status_string(status));
        return EXIT_FAILURE;
    }
    if (strcmp(output, "Goodbye, Ada!") != 0) {
        (void)fprintf(stderr, "unexpected farewell: %s\n", output);
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
