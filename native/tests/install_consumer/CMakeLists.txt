cmake_minimum_required(VERSION 3.25)

project(native_install_consumer LANGUAGES CXX)

find_package(MonorepoTemplate CONFIG REQUIRED)

add_executable(native_install_consumer main.cpp)
target_compile_features(native_install_consumer PRIVATE cxx_std_17)
target_link_libraries(
  native_install_consumer
  PRIVATE
    example::package_a
    example::package_b
)

enable_testing()
add_test(NAME installed.native.cpp_consumer COMMAND native_install_consumer)
