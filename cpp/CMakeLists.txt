cmake_minimum_required(VERSION 3.20)
project(pguard_native LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_C_VISIBILITY_PRESET hidden)
option(PGUARD_CUDA "Build the optional CUDA kernel (needs an NVIDIA toolchain)" OFF)

add_library(pguard_native SHARED src/signal.cpp driver/pg_shim.c)
target_include_directories(pguard_native PUBLIC include)
target_compile_options(pguard_native PRIVATE
  $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall -Wextra -Wpedantic -Werror>)
if(WIN32)
  set_target_properties(pguard_native PROPERTIES PREFIX "")
endif()
if(MINGW)
  # Self-contained DLL: Python on Windows does not search the MinGW runtime directory.
  target_link_options(pguard_native PRIVATE -static)
endif()

enable_testing()
add_executable(test_signal tests/test_signal.cpp)
target_link_libraries(test_signal PRIVATE pguard_native)
add_test(NAME signal COMMAND test_signal)

if(PGUARD_CUDA)
  enable_language(CUDA)
  add_library(pguard_cuda SHARED cuda/window_std.cu)
  target_include_directories(pguard_cuda PUBLIC include)
endif()
