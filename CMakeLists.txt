cmake_minimum_required(VERSION 3.25)

project(
  monorepo_template
  VERSION 0.1.1 # x-release-please-version
  DESCRIPTION "Production-oriented C component examples"
  LANGUAGES C
)

include(GNUInstallDirs)
include(CTest)
include(CMakePackageConfigHelpers)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(ProjectOptions)
include(StaticAnalysis)

monorepo_add_clang_format_targets()

add_subdirectory(native/packages/core)
add_subdirectory(native/packages/package_a)
add_subdirectory(native/packages/package_b)
add_subdirectory(native/apps/package_a_cli)

configure_package_config_file(
  cmake/MonorepoTemplateConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/MonorepoTemplateConfig.cmake"
  INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/monorepo-template"
)
write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/MonorepoTemplateConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion
)

install(
  EXPORT MonorepoTemplateTargets
  FILE MonorepoTemplateTargets.cmake
  NAMESPACE example::
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/monorepo-template"
)
install(
  FILES
    "${CMAKE_CURRENT_BINARY_DIR}/MonorepoTemplateConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/MonorepoTemplateConfigVersion.cmake"
  DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/monorepo-template"
)
