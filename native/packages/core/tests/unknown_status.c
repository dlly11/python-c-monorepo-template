#include "example/core.h"

const char *example_test_unknown_status_string(void);

/* C permits this value; converting 99 to this enum in C++ would be undefined. */
const char *example_test_unknown_status_string(void) {
    return example_core_status_string((example_status)99);
}
