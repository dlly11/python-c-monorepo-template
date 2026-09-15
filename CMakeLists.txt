cmake_minimum_required(VERSION 3.25)

project(
  monorepo_template
  VERSION 1.0.2 # x-release-please-version
  DESCRIPTION "Production-oriented C component examples"
  LANGUAGES C
)

include(GNUInstallDirs)
include(CTest)
include(CMakePackageConfigHelpers)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(ProjectOptions)
include(StaticAnalysis)
include(VersionHeaders)

monorepo_add_clang_format_targets()

if(BUILD_TESTING)
  enable_language(CXX)
  include(CppUTest)
  monorepo_add_cpputest()

  add_library(example_cpputest_main STATIC native/tests/cpputest_main.cpp)
  target_link_libraries(example_cpputest_main PUBLIC CppUTest::CppUTest)
  monorepo_set_cpp_test_options(example_cpputest_main)
endif()

add_subdirectory(native/packages/core)
add_subdirectory(native/packages/package_a)
add_subdirectory(native/packages/package_b)
add_subdirectory(native/apps/package_a_cli)

set(monorepo_cmake_install_directory "${CMAKE_INSTALL_LIBDIR}/cmake/MonorepoTemplate")
configure_package_config_file(
  cmake/MonorepoTemplateConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/MonorepoTemplateConfig.cmake"
  INSTALL_DESTINATION "${monorepo_cmake_install_directory}"
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
  DESTINATION "${monorepo_cmake_install_directory}"
)
install(
  FILES
    "${CMAKE_CURRENT_BINARY_DIR}/MonorepoTemplateConfig.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/MonorepoTemplateConfigVersion.cmake"
  DESTINATION "${monorepo_cmake_install_directory}"
)
