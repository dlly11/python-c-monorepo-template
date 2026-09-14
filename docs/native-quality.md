# Native quality gates

## clang-format

`.clang-format` is the single source of formatting policy for C source and headers.

```bash
cmake --build --preset dev --target format-c
cmake --build --preset dev --target format-c-check
```

The first command changes files. The second is read-only and is the appropriate CI gate.

## clang-tidy

`.clang-tidy` enables compiler diagnostics, Clang's static analyzer, CERT-oriented checks, and
portability checks. It is connected to targets through CMake's `C_CLANG_TIDY` target property,
which supplies the exact compiler command and include paths.

## cppcheck

Cppcheck complements clang-tidy with a separate analysis engine. The CMake analysis preset runs
it with warning, style, performance, and portability checks enabled. Missing system includes are
suppressed because those headers are owned by the selected compiler toolchain.

## Policy levels

| Workflow | Intended use | Static analysis |
| --- | --- | --- |
| `dev` | Normal local builds | Available separately; not required |
| `analysis` | Pull requests and release qualification | clang-tidy and cppcheck required |
| `asan` | Runtime defect detection | AddressSanitizer and UndefinedBehaviorSanitizer |
| `coverage` | Native test effectiveness | GCC/gcov line and branch coverage |
| `release` | Optimized artifacts | Tests and analysis performed in earlier stages |

Compiler warnings are errors in `dev`, `analysis`, and `asan`. Release consumers do not inherit
the repository's private warning flags.
