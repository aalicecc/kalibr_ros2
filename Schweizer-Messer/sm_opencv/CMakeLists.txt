cmake_minimum_required(VERSION 3.8)
project(sm_opencv)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(sm_common REQUIRED)
find_package(Boost REQUIRED COMPONENTS system)

add_definitions(-D__STRICT_ANSI__)

install(DIRECTORY include/
  DESTINATION include
)

ament_export_include_directories(include)
ament_export_dependencies(sm_common Boost)
ament_package()
