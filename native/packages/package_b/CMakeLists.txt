add_library(example_package_b STATIC src/package_b.c)
add_library(example::package_b ALIAS example_package_b)

target_include_directories(
  example_package_b
  PUBLIC
    "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>"
)
target_link_libraries(example_package_b PUBLIC example::core)
set_target_properties(example_package_b PROPERTIES EXPORT_NAME package_b)
monorepo_set_project_options(example_package_b)

install(
  TARGETS example_package_b
  EXPORT MonorepoTemplateTargets
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(DIRECTORY include/ DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")

if(BUILD_TESTING)
  add_executable(example_package_b_tests tests/test_package_b.c)
  target_link_libraries(example_package_b_tests PRIVATE example::package_b)
  monorepo_set_project_options(example_package_b_tests)
  add_test(NAME c.package_b COMMAND example_package_b_tests)
endif()
