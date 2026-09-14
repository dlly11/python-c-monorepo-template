#ifndef EXAMPLE_PACKAGE_B_H
#define EXAMPLE_PACKAGE_B_H

#include "example/core.h"

#include <stddef.h>

/**
 * Create a farewell using the shared core formatter.
 *
 * @param[in] name Non-empty recipient name.
 * @param[out] output Destination buffer.
 * @param[in] output_capacity Size of @p output in bytes.
 * @return EXAMPLE_STATUS_OK on success, or a status describing the failure.
 */
example_status example_package_b_farewell(const char *name, char *output, size_t output_capacity);

#endif
