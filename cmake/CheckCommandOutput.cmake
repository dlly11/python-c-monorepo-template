if(NOT DEFINED COMMAND_PATH OR NOT DEFINED COMMAND_ARGUMENT OR NOT DEFINED EXPECTED_OUTPUT)
  message(FATAL_ERROR "COMMAND_PATH, COMMAND_ARGUMENT, and EXPECTED_OUTPUT are required")
endif()

execute_process(
  COMMAND "${COMMAND_PATH}" "${COMMAND_ARGUMENT}"
  RESULT_VARIABLE command_status
  OUTPUT_VARIABLE command_output
  ERROR_VARIABLE command_error
)

if(NOT command_status EQUAL 0)
  message(FATAL_ERROR "Command exited with ${command_status}: ${command_error}")
endif()

string(REPLACE "\r\n" "\n" normalized_output "${command_output}")
if(NOT normalized_output STREQUAL "${EXPECTED_OUTPUT}\n")
  message(
    FATAL_ERROR
    "Expected exact output '${EXPECTED_OUTPUT}\\n', received '${normalized_output}'"
  )
endif()

if(NOT command_error STREQUAL "")
  message(FATAL_ERROR "Command wrote unexpected standard error: ${command_error}")
endif()
