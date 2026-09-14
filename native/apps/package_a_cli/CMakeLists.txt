add_executable(example_package_a_cli src/main.c)
target_link_libraries(example_package_a_cli PRIVATE example::package_a)
set_target_properties(example_package_a_cli PROPERTIES OUTPUT_NAME package-a-cli)
monorepo_set_project_options(example_package_a_cli)

install(TARGETS example_package_a_cli RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")

if(BUILD_TESTING)
  add_test(NAME c.package_a_cli COMMAND example_package_a_cli Ada)
  set_tests_properties(c.package_a_cli PROPERTIES PASS_REGULAR_EXPRESSION "Hello, Ada!")

  add_test(NAME c.package_a_cli.usage COMMAND example_package_a_cli)
  set_tests_properties(c.package_a_cli.usage PROPERTIES WILL_FAIL TRUE)
endif()
