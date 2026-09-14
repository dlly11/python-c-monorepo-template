# Native package A CLI examples

Build the application and its dependencies:

```bash
cmake --preset dev
cmake --build --preset dev
```

Run it with exactly one name argument:

```console
$ ./build/dev/native/apps/package_a_cli/package-a-cli Ada
Hello, Ada!
```

Quote names containing spaces:

```console
$ ./build/dev/native/apps/package_a_cli/package-a-cli "Ada Lovelace"
Hello, Ada Lovelace!
```

Print the application version:

```console
$ ./build/dev/native/apps/package_a_cli/package-a-cli --version
package-a-cli X.Y.Z
```

`X.Y.Z` is the current value from `version.txt` and the generated CLI version header.
