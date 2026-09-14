#include "example/package_b.h"

example_status example_package_b_farewell(const char *name, char *output, size_t output_capacity) {
    return example_core_format_message("Goodbye", name, output, output_capacity);
}
