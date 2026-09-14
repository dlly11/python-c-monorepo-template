#include "example/package_a.h"
#include "example/package_a_cli_version.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    char output[256] = {0};
    example_status status = EXAMPLE_STATUS_OK;

    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        if (printf("package-a-cli %s\n", EXAMPLE_PACKAGE_A_CLI_VERSION) < 0) {
            return EXIT_FAILURE;
        }
        return EXIT_SUCCESS;
    }

    if (argc != 2) {
        (void)fprintf(stderr, "usage: %s NAME\n", argv[0]);
        return EXIT_FAILURE;
    }

    status = example_package_a_greeting(argv[1], output, sizeof(output));
    if (status != EXAMPLE_STATUS_OK) {
        (void)fprintf(stderr, "package-a-cli: %s\n", example_core_status_string(status));
        return EXIT_FAILURE;
    }

    if (puts(output) == EOF) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
