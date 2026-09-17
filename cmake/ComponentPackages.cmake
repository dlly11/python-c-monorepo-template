include_guard(GLOBAL)

function(monorepo_component target component package)
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/version.txt")
  file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/version.txt" component_version)
  if(NOT component_version MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+$")
    message(FATAL_ERROR "Invalid component version in ${CMAKE_CURRENT_SOURCE_DIR}/version.txt")
  endif()
  set_target_properties(${target} PROPERTIES
    MONOREPO_VERSION "${component_version}"
    MONOREPO_COMPONENT "${component}"
    MONOREPO_PACKAGE "${package}"
  )
endfunction()

function(monorepo_install_component target)
  get_target_property(component ${target} MONOREPO_COMPONENT)
  get_target_property(package ${target} MONOREPO_PACKAGE)
  get_target_property(component_version ${target} MONOREPO_VERSION)
  get_target_property(kind ${target} TYPE)
  set(directory "${CMAKE_INSTALL_LIBDIR}/cmake/${package}")
  set(dependencies "")
  set(provenance "${component}=${component_version}\n")
  foreach(dependency IN LISTS ARGN)
    get_target_property(dependency_package ${dependency} MONOREPO_PACKAGE)
    get_target_property(dependency_version ${dependency} MONOREPO_VERSION)
    get_target_property(dependency_provenance ${dependency} MONOREPO_PROVENANCE)
    string(APPEND provenance "${dependency_provenance}")
    # Static executables already contain their linked libraries.
    if(NOT kind STREQUAL "EXECUTABLE")
      string(APPEND dependencies "find_dependency(${dependency_package} ${dependency_version} CONFIG)\n")
    endif()
  endforeach()
  set_target_properties(${target} PROPERTIES MONOREPO_PROVENANCE "${provenance}")
  file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/component-versions.txt" "${provenance}")
  configure_package_config_file(
    "${PROJECT_SOURCE_DIR}/cmake/ComponentConfig.cmake.in"
    "${CMAKE_CURRENT_BINARY_DIR}/${package}Config.cmake"
    INSTALL_DESTINATION "${directory}"
  )
  write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/${package}ConfigVersion.cmake"
    VERSION "${component_version}"
    COMPATIBILITY SameMajorVersion
  )
  install(TARGETS ${target} EXPORT ${package}Targets
    RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}" COMPONENT ${component}
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}" COMPONENT ${component}
    INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
  )
  install(EXPORT ${package}Targets FILE ${package}Targets.cmake
    NAMESPACE example:: DESTINATION "${directory}" COMPONENT ${component}
  )
  install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/${package}Config.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/${package}ConfigVersion.cmake"
    DESTINATION "${directory}" COMPONENT ${component}
  )
  install(DIRECTORY include/ DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
    COMPONENT ${component} FILES_MATCHING PATTERN "*.h"
  )
  install(FILES "${CMAKE_CURRENT_BINARY_DIR}/component-versions.txt"
    DESTINATION "${CMAKE_INSTALL_DATADIR}/${component}" COMPONENT ${component}
  )
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE")
    install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE"
      DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/${component}" COMPONENT ${component})
  elseif(EXISTS "${PROJECT_SOURCE_DIR}/LICENSE")
    install(FILES "${PROJECT_SOURCE_DIR}/LICENSE"
      DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/${component}" COMPONENT ${component})
  endif()
endfunction()
