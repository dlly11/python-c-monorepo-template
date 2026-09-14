# Native package B examples

```c
#include <example/package_b.h>

#include <stdio.h>

int main(void) {
    char message[64] = {0};
    example_status status = example_package_b_farewell("Ada", message, sizeof(message));

    if (status != EXAMPLE_STATUS_OK) {
        return 1;
    }

    (void)puts(message);
    return 0;
}
```

Read the configured package version at compile time:

```c
#include <example/package_b_version.h>

const char *package_b_version = EXAMPLE_PACKAGE_B_VERSION;
```

Within this repository, save the example as `example.c` and compile it directly with:

```bash
cc -std=c17 -Inative/packages/core/include -Inative/packages/package_b/include \
  native/packages/core/src/core.c native/packages/package_b/src/package_b.c \
  example.c -o package-b-example
./package-b-example
```
