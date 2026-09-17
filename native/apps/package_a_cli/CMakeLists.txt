add_executable(example_package_a_cli src/main.c)
monorepo_component(example_package_a_cli native-package-a-cli ExamplePackageACli)
target_link_libraries(example_package_a_cli PRIVATE example::package_a)
monorepo_add_version_header(
  example_package_a_cli
  "${CMAKE_CURRENT_SOURCE_DIR}/include/example/package_a_cli_version.h.in"
  "example/package_a_cli_version.h"
  PRIVATE
)
set_target_properties(example_package_a_cli PROPERTIES OUTPUT_NAME package-a-cli)
monorepo_set_project_options(example_package_a_cli)

set_target_properties(example_package_a_cli PROPERTIES EXPORT_NAME package_a_cli)
monorepo_install_component(example_package_a_cli example_package_a)
get_target_property(cli_version example_package_a_cli MONOREPO_VERSION)

if(BUILD_TESTING)
  # Optional fifth argument is passed verbatim, including an empty name. The sixth
  # redirects stdout for Linux output-failure tests.
  function(monorepo_add_cli_test name status stdout stderr)
    set(command_options
      "-DCOMMAND_PATH=$<TARGET_FILE:example_package_a_cli>"
      "-DEXPECTED_EXIT_CODE=${status}"
      "-DEXPECTED_STDOUT=${stdout}"
      "-DEXPECTED_STDERR=${stderr}"
    )
    if(ARGC GREATER 4)
      list(APPEND command_options "-DCOMMAND_ARGUMENT=${ARGV4}")
    endif()
    if(ARGC GREATER 5)
      list(APPEND command_options "-DSTDOUT_FILE=${ARGV5}")
    endif()
    add_test(
      NAME "${name}"
      COMMAND "${CMAKE_COMMAND}" ${command_options}
        -P "${PROJECT_SOURCE_DIR}/cmake/CheckCommandOutput.cmake"
    )
    set_tests_properties("${name}" PROPERTIES TIMEOUT 60)
  endfunction()

  monorepo_add_cli_test(c.package_a_cli 0 "Hello, Ada!\n" "" "Ada")
  monorepo_add_cli_test(
    c.package_a_cli.version 0 "package-a-cli ${cli_version}\n" "" "--version"
  )
  monorepo_add_cli_test(
    c.package_a_cli.usage 1 "" "usage: $<TARGET_FILE:example_package_a_cli> NAME\n"
  )
  monorepo_add_cli_test(
    c.package_a_cli.empty_name 1 "" "package-a-cli: invalid argument\n" ""
  )
  string(REPEAT "x" 256 package_a_cli_oversized_name)
  monorepo_add_cli_test(
    c.package_a_cli.buffer_too_small 1 "" "package-a-cli: buffer too small\n"
    "${package_a_cli_oversized_name}"
  )

  if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    monorepo_add_cli_test(c.package_a_cli.output_failure 1 "" "" "Ada" "/dev/full")
    monorepo_add_cli_test(c.package_a_cli.version_output_failure 1 "" "" "--version" "/dev/full")
  endif()
endif()
