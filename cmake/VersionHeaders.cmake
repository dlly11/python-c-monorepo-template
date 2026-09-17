include_guard(GLOBAL)

function(monorepo_add_version_header target template relative_header visibility)
  if(NOT TARGET ${target})
    message(FATAL_ERROR "Cannot add a version header to unknown target: ${target}")
  endif()

  set(generated_include_directory "${CMAKE_BINARY_DIR}/generated/include")
  get_target_property(PROJECT_VERSION ${target} MONOREPO_VERSION)
  get_target_property(component ${target} MONOREPO_COMPONENT)
  string(REPLACE "." ";" version_parts "${PROJECT_VERSION}")
  list(GET version_parts 0 PROJECT_VERSION_MAJOR)
  list(GET version_parts 1 PROJECT_VERSION_MINOR)
  list(GET version_parts 2 PROJECT_VERSION_PATCH)
  set(generated_header "${generated_include_directory}/${relative_header}")
  get_filename_component(generated_header_directory "${generated_header}" DIRECTORY)
  get_filename_component(install_header_directory "${relative_header}" DIRECTORY)

  file(MAKE_DIRECTORY "${generated_header_directory}")
  configure_file("${template}" "${generated_header}" @ONLY)

  target_include_directories(
    ${target}
    ${visibility}
      "$<BUILD_INTERFACE:${generated_include_directory}>"
  )
  install(
    FILES "${generated_header}"
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/${install_header_directory}"
    COMPONENT ${component}
  )
endfunction()

function(monorepo_set_version_test_definitions target component_target)
  get_target_property(component_version ${component_target} MONOREPO_VERSION)
  string(REPLACE "." ";" version_parts "${component_version}")
  list(GET version_parts 0 major)
  list(GET version_parts 1 minor)
  list(GET version_parts 2 patch)
  target_compile_definitions(
    ${target}
    PRIVATE
      EXAMPLE_EXPECTED_VERSION="${component_version}"
      EXAMPLE_EXPECTED_VERSION_MAJOR=${major}
      EXAMPLE_EXPECTED_VERSION_MINOR=${minor}
      EXAMPLE_EXPECTED_VERSION_PATCH=${patch}
  )
endfunction()
