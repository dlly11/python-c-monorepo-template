# Native package A examples

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

Within this repository, save the example as `example.c` and compile it directly with:

```bash
cc -std=c17 -Inative/packages/core/include -Inative/packages/package_a/include \
  native/packages/core/src/core.c native/packages/package_a/src/package_a.c \
  example.c -o package-a-example
./package-a-example
```
