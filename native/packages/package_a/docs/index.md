# Native package A

The native package A library creates greetings through the core formatter. Consumers include
`<example/package_a.h>` for behaviour, `<example/package_a_version.h>` for version macros, and link
to `example::package_a`.

```cmake
target_link_libraries(my_target PRIVATE example::package_a)
```

## Native package A examples

```c
#include <example/package_a.h>

#include <stdio.h>

int main(void) {
    char message[64] = {0};
    example_status status = example_package_a_greeting("Ada", message, sizeof(message));

    if (status != EXAMPLE_STATUS_OK) {
        return 1;
    }

    (void)puts(message);
    return 0;
}
```

Read the configured package version at compile time:

```c
#include <example/package_a_version.h>

const char *package_a_version = EXAMPLE_PACKAGE_A_VERSION;
```

Within this repository, save the example as `example.c` and compile it directly with:

```bash
cc -std=c17 -Inative/packages/core/include -Inative/packages/package_a/include \
  native/packages/core/src/core.c native/packages/package_a/src/package_a.c \
  example.c -o package-a-example
./package-a-example
```

## Native package A API

```{doxygenfunction} example_package_a_greeting
:project: native
```

### Version macros

```{doxygendefine} EXAMPLE_PACKAGE_A_VERSION
:project: native
```

```{doxygendefine} EXAMPLE_PACKAGE_A_VERSION_MAJOR
:project: native
```

```{doxygendefine} EXAMPLE_PACKAGE_A_VERSION_MINOR
:project: native
```

```{doxygendefine} EXAMPLE_PACKAGE_A_VERSION_PATCH
:project: native
```
