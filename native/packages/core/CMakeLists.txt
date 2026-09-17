add_library(example_core STATIC src/core.c)
monorepo_component(example_core native-core ExampleCore)
add_library(example::core ALIAS example_core)

target_include_directories(
  example_core
  PUBLIC
    "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>"
)
monorepo_add_version_header(
  example_core
  "${CMAKE_CURRENT_SOURCE_DIR}/include/example/core_version.h.in"
  "example/core_version.h"
  PUBLIC
)
set_target_properties(example_core PROPERTIES EXPORT_NAME core)
monorepo_set_project_options(example_core)

monorepo_install_component(example_core)

if(BUILD_TESTING)
  add_library(example_core_c_test_helpers OBJECT tests/unknown_status.c)
  target_link_libraries(example_core_c_test_helpers PRIVATE example::core)
  monorepo_set_project_options(example_core_c_test_helpers)

  add_executable(example_core_tests tests/test_core.cpp)
  target_link_libraries(example_core_tests PRIVATE example::core example_cpputest_main example_core_c_test_helpers)
  monorepo_set_cpp_test_options(example_core_tests)
  monorepo_set_version_test_definitions(example_core_tests example_core)
  add_test(NAME c.core COMMAND example_core_tests)
  set_tests_properties(c.core PROPERTIES TIMEOUT 60)
endif()
