# Changelog

## [3.0.0](https://github.com/dlly11/python-c-monorepo-template/compare/native-package-a-v2.0.4...native-package-a-v3.0.0) (2026-09-17)


### ⚠ BREAKING CHANGES

* **release:** Native consumers must replace find_package(MonorepoTemplate) with component packages such as ExampleCore or ExamplePackageA. Native archives and product tags are component-specific. The set-version command now requires a component ID before the version.

### Features

* **release:** version products independently and add commit tooling ([65b44cf](https://github.com/dlly11/python-c-monorepo-template/commit/65b44cffa80b3e209e5160ae65cc311d9e7e0f8b))

## 2.0.4

Independent version baseline. Earlier releases are recorded in the repository changelog.
