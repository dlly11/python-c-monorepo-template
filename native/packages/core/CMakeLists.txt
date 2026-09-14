add_library(example_core STATIC src/core.c)
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

install(
  TARGETS example_core
  EXPORT MonorepoTemplateTargets
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(
  DIRECTORY include/
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
  FILES_MATCHING
  PATTERN "*.h"
)

if(BUILD_TESTING)
  add_executable(example_core_tests tests/test_core.cpp)
  target_link_libraries(example_core_tests PRIVATE example::core example_cpputest_main)
  monorepo_set_cpp_test_options(example_core_tests)
  monorepo_set_version_test_definitions(example_core_tests)
  add_test(NAME c.core COMMAND example_core_tests)
endif()
