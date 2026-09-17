add_library(example_package_a STATIC src/package_a.c)
monorepo_component(example_package_a native-package-a ExamplePackageA)
add_library(example::package_a ALIAS example_package_a)

target_include_directories(
  example_package_a
  PUBLIC
    "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>"
)
monorepo_add_version_header(
  example_package_a
  "${CMAKE_CURRENT_SOURCE_DIR}/include/example/package_a_version.h.in"
  "example/package_a_version.h"
  PUBLIC
)
target_link_libraries(example_package_a PUBLIC example::core)
set_target_properties(example_package_a PROPERTIES EXPORT_NAME package_a)
monorepo_set_project_options(example_package_a)

monorepo_install_component(example_package_a example_core)

if(BUILD_TESTING)
  add_executable(example_package_a_tests tests/test_package_a.cpp)
  target_link_libraries(example_package_a_tests PRIVATE example::package_a example_cpputest_main)
  monorepo_set_cpp_test_options(example_package_a_tests)
  monorepo_set_version_test_definitions(example_package_a_tests example_package_a)
  add_test(NAME c.package_a COMMAND example_package_a_tests)
  set_tests_properties(c.package_a PROPERTIES TIMEOUT 60)
endif()
