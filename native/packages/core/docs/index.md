# Native core

The native core library owns the shared `example_status` contract and bounded message formatter.
Consumers include `<example/core.h>` for behaviour, `<example/core_version.h>` for version macros,
and link to the CMake target `example::core`.

```cmake
target_link_libraries(my_target PRIVATE example::core)
```

## Native core examples

```c
#include <example/core.h>

#include <stdio.h>

int main(void) {
    char message[64] = {0};
    example_status status =
        example_core_format_message("Welcome", "Ada", message, sizeof(message));

    if (status != EXAMPLE_STATUS_OK) {
        (void)fprintf(stderr, "%s\n", example_core_status_string(status));
        return 1;
    }

    (void)puts(message);
    return 0;
}
```

Read the configured library version at compile time:

```c
#include <example/core_version.h>

const char *core_version = EXAMPLE_CORE_VERSION;
```

Within this repository, save the example as `example.c` and compile it directly with:

```bash
cc -std=c17 -Inative/packages/core/include \
  native/packages/core/src/core.c example.c -o core-example
./core-example
```

## Native core API

```{doxygenenum} example_status
:project: native
```

```{doxygenfunction} example_core_format_message
:project: native
```

```{doxygenfunction} example_core_status_string
:project: native
```

### Version macros

```{doxygendefine} EXAMPLE_CORE_VERSION
:project: native
```

```{doxygendefine} EXAMPLE_CORE_VERSION_MAJOR
:project: native
```

```{doxygendefine} EXAMPLE_CORE_VERSION_MINOR
:project: native
```

```{doxygendefine} EXAMPLE_CORE_VERSION_PATCH
:project: native
```
