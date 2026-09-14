# Native package B

The native package B library creates farewells through the core formatter. Consumers include
`<example/package_b.h>` for behaviour, `<example/package_b_version.h>` for version macros, and link
to `example::package_b`.

```cmake
target_link_libraries(my_target PRIVATE example::package_b)
```

```{toctree}
:maxdepth: 1

examples
api
```
