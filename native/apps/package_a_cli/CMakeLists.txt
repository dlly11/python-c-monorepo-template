add_executable(example_package_a_cli src/main.c)
target_link_libraries(example_package_a_cli PRIVATE example::package_a)
monorepo_add_version_header(
  example_package_a_cli
  "${CMAKE_CURRENT_SOURCE_DIR}/include/example/package_a_cli_version.h.in"
  "example/package_a_cli_version.h"
  PRIVATE
)
set_target_properties(example_package_a_cli PROPERTIES OUTPUT_NAME package-a-cli)
monorepo_set_project_options(example_package_a_cli)

install(TARGETS example_package_a_cli RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")

if(BUILD_TESTING)
  add_test(NAME c.package_a_cli COMMAND example_package_a_cli Ada)
  set_tests_properties(c.package_a_cli PROPERTIES PASS_REGULAR_EXPRESSION "Hello, Ada!")

  add_test(
    NAME c.package_a_cli.version
    COMMAND
      "${CMAKE_COMMAND}"
      "-DCOMMAND_PATH=$<TARGET_FILE:example_package_a_cli>"
      "-DCOMMAND_ARGUMENT=--version"
      "-DEXPECTED_OUTPUT=package-a-cli ${CMAKE_PROJECT_VERSION}"
      -P "${PROJECT_SOURCE_DIR}/cmake/CheckCommandOutput.cmake"
  )

  add_test(NAME c.package_a_cli.usage COMMAND example_package_a_cli)
  set_tests_properties(c.package_a_cli.usage PROPERTIES WILL_FAIL TRUE)

  string(REPEAT "x" 256 package_a_cli_oversized_name)
  add_test(
    NAME c.package_a_cli.buffer_too_small
    COMMAND example_package_a_cli "${package_a_cli_oversized_name}"
  )
  set_tests_properties(
    c.package_a_cli.buffer_too_small
    PROPERTIES
      PASS_REGULAR_EXPRESSION "buffer too small"
  )
endif()
