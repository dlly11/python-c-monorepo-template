# Native core examples

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

Within this repository, save the example as `example.c` and compile it directly with:

```bash
cc -std=c17 -Inative/packages/core/include \
  native/packages/core/src/core.c example.c -o core-example
./core-example
```
