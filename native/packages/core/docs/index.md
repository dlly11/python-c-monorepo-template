# Native core

The native core library owns the shared `example_status` contract and bounded message formatter.
Consumers include `<example/core.h>` for behaviour, `<example/core_version.h>` for version macros,
and link to the CMake target `example::core`.

```cmake
target_link_libraries(my_target PRIVATE example::core)
```

```{toctree}
:maxdepth: 1

examples
api
```
