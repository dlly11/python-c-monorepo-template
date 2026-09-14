#include "example/core.h"

#include <stdio.h>

example_status example_core_format_message(const char *prefix, const char *name, char *output,
                                           size_t output_capacity) {
    int characters_written = 0;

    if (prefix == NULL || name == NULL || output == NULL || output_capacity == 0U ||
        prefix[0] == '\0' || name[0] == '\0') {
        return EXAMPLE_STATUS_INVALID_ARGUMENT;
    }

    characters_written = snprintf(output, output_capacity, "%s, %s!", prefix, name);
    if (characters_written < 0) {
        output[0] = '\0';
        return EXAMPLE_STATUS_FORMAT_ERROR;
    }
    if ((size_t)characters_written >= output_capacity) {
        return EXAMPLE_STATUS_BUFFER_TOO_SMALL;
    }
    return EXAMPLE_STATUS_OK;
}

const char *example_core_status_string(example_status status) {
    switch (status) {
    case EXAMPLE_STATUS_OK:
        return "ok";
    case EXAMPLE_STATUS_INVALID_ARGUMENT:
        return "invalid argument";
    case EXAMPLE_STATUS_BUFFER_TOO_SMALL:
        return "buffer too small";
    case EXAMPLE_STATUS_FORMAT_ERROR:
        return "format error";
    default:
        return "unknown status";
    }
}
