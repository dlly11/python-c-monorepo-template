include_guard(GLOBAL)

option(WARNINGS_AS_ERRORS "Treat compiler warnings as errors" OFF)
option(ENABLE_SANITIZERS "Enable address and undefined behaviour sanitizers" OFF)

function(monorepo_set_project_options target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4)
    if(WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE /WX)
    endif()
  else()
    target_compile_options(
      ${target}
      PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Wconversion
        -Wshadow
        -Wstrict-prototypes
        -Wmissing-prototypes
    )
    if(WARNINGS_AS_ERRORS)
      target_compile_options(${target} PRIVATE -Werror)
    endif()
  endif()

  set_target_properties(
    ${target}
    PROPERTIES
      C_STANDARD 17
      C_STANDARD_REQUIRED YES
      C_EXTENSIONS NO
  )

  if(ENABLE_SANITIZERS)
    if(MSVC)
      message(FATAL_ERROR "The sanitizer preset is currently supported only with GCC or Clang")
    endif()
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endif()

  monorepo_enable_static_analysis(${target})
endfunction()
