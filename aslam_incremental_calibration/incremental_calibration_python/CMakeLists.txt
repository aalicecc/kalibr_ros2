cmake_minimum_required(VERSION 3.8)
project(incremental_calibration_python)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(incremental_calibration REQUIRED)
find_package(sm_property_tree REQUIRED)
find_package(numpy_eigen REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  system thread serialization filesystem regex)

add_python_export_library(${PROJECT_NAME} src/incremental_calibration
  src/module.cpp
  src/OptimizationProblem.cpp
  src/IncrementalEstimator.cpp
  src/LinearSolver.cpp
)
target_include_directories(${PROJECT_NAME} PRIVATE include)
ament_target_dependencies(${PROJECT_NAME}
  aslam_backend incremental_calibration sm_property_tree numpy_eigen)

ament_python_install_package(incremental_calibration
  PACKAGE_DIR src/incremental_calibration)
install(DIRECTORY include/ DESTINATION include)

ament_export_include_directories(include)
ament_export_dependencies(aslam_backend incremental_calibration
  sm_property_tree numpy_eigen)
ament_package()
