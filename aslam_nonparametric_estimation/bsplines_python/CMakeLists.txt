cmake_minimum_required(VERSION 3.8)
project(bsplines_python)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(bsplines REQUIRED)
find_package(numpy_eigen REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  system thread serialization filesystem regex)

add_python_export_library(${PROJECT_NAME} python/bsplines
  src/SplinePython.cpp
  src/BSplinePython.cpp
  src/BSplinePosePython.cpp
)
ament_target_dependencies(${PROJECT_NAME}
  bsplines numpy_eigen sparse_block_matrix sm_common sm_kinematics)

ament_python_install_package(bsplines PACKAGE_DIR python/bsplines)
ament_export_dependencies(bsplines numpy_eigen sparse_block_matrix
  sm_common sm_kinematics)
ament_package()
