#ifndef EXAMPLE_CORE_H
#define EXAMPLE_CORE_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Status returned by the example native APIs. */
typedef enum example_status {
    /** The operation completed successfully. */
    EXAMPLE_STATUS_OK = 0,
    /** A required pointer, string, or capacity was invalid. */
    EXAMPLE_STATUS_INVALID_ARGUMENT = 1,
    /** The output buffer could not hold the complete formatted message. */
    EXAMPLE_STATUS_BUFFER_TOO_SMALL = 2,
    /** The C runtime could not format the message. */
    EXAMPLE_STATUS_FORMAT_ERROR = 3
} example_status;

/**
 * Format a message as ``prefix, name!``.
 *
 * @param[in] prefix Non-empty message prefix.
 * @param[in] name Non-empty recipient name.
 * @param[out] output Destination buffer.
 * @param[in] output_capacity Size of @p output in bytes.
 * @return EXAMPLE_STATUS_OK on success, or a status describing the failure.
 */
example_status example_core_format_message(const char *prefix, const char *name, char *output,
                                           size_t output_capacity);

/**
 * Return a stable human-readable description of a status.
 *
 * @param[in] status Status to describe.
 * @return A pointer to a static, null-terminated string.
 */
const char *example_core_status_string(example_status status);

#ifdef __cplusplus
}
#endif

#endif
