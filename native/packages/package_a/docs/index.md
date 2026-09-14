# Native package A

The native package A library creates greetings through the core formatter. Consumers include
`<example/package_a.h>` for behaviour, `<example/package_a_version.h>` for version macros, and link
to `example::package_a`.

```cmake
target_link_libraries(my_target PRIVATE example::package_a)
```

```{toctree}
:maxdepth: 1

examples
api
```
