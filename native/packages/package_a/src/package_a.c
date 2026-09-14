#include "example/package_a.h"

example_status example_package_a_greeting(const char *name, char *output, size_t output_capacity) {
    return example_core_format_message("Hello", name, output, output_capacity);
}
