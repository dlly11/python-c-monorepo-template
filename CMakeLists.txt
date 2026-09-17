cmake_minimum_required(VERSION 3.25)

project(
  monorepo_template
  VERSION 3.0.0 # x-release-please-version
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
include(ComponentPackages)

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
