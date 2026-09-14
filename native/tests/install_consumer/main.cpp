#include "example/core.h"
#include "example/core_version.h"
#include "example/package_a.h"
#include "example/package_a_cli_version.h"
#include "example/package_a_version.h"
#include "example/package_b.h"
#include "example/package_b_version.h"

#include <cstring>

int main() {
    char greeting[64] = {0};
    char farewell[64] = {0};

    if (example_package_a_greeting("Ada", greeting, sizeof(greeting)) != EXAMPLE_STATUS_OK ||
        example_package_b_farewell("Ada", farewell, sizeof(farewell)) != EXAMPLE_STATUS_OK) {
        return 1;
    }
    if (std::strcmp(greeting, "Hello, Ada!") != 0 || std::strcmp(farewell, "Goodbye, Ada!") != 0) {
        return 2;
    }
    if (std::strcmp(EXAMPLE_CORE_VERSION, EXAMPLE_PACKAGE_A_VERSION) != 0 ||
        std::strcmp(EXAMPLE_CORE_VERSION, EXAMPLE_PACKAGE_B_VERSION) != 0 ||
        std::strcmp(EXAMPLE_CORE_VERSION, EXAMPLE_PACKAGE_A_CLI_VERSION) != 0) {
        return 3;
    }
    return 0;
}
