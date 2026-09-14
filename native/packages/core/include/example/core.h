#ifndef EXAMPLE_CORE_H
#define EXAMPLE_CORE_H

#include <stddef.h>

typedef enum example_status {
    EXAMPLE_STATUS_OK = 0,
    EXAMPLE_STATUS_INVALID_ARGUMENT = 1,
    EXAMPLE_STATUS_BUFFER_TOO_SMALL = 2,
    EXAMPLE_STATUS_FORMAT_ERROR = 3
} example_status;

example_status example_core_format_message(const char *prefix, const char *name, char *output,
                                           size_t output_capacity);

const char *example_core_status_string(example_status status);

#endif
