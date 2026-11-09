cmake_minimum_required(VERSION 3.8)
project(aslam_backend_python)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(aslam_backend_expressions REQUIRED)
find_package(numpy_eigen REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(sm_timing REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  system thread serialization filesystem regex)

add_python_export_library(${PROJECT_NAME} python/aslam_backend
  src/module.cpp
  src/Backend.cpp
  src/Optimizer.cpp
  src/OptimizerOptions.cpp
  src/OptimizationProblem.cpp
  src/DesignVariable.cpp
  src/ErrorTerm.cpp
  src/MEstimators.cpp
  src/JacobianContainer.cpp
  src/BackendExpressions.cpp
  src/CompressedColumnMatrix.cpp
  src/LinearSystemSolver.cpp
  src/ErrorTermTransformation.cpp
  src/TrustRegionPolicies.cpp
  src/SparseBlockMatrix.cpp
)
target_include_directories(${PROJECT_NAME} PRIVATE include)
target_link_libraries(${PROJECT_NAME} Boost::thread)
ament_target_dependencies(${PROJECT_NAME}
  aslam_backend aslam_backend_expressions numpy_eigen sparse_block_matrix
  sm_common sm_kinematics sm_timing)

ament_python_install_package(aslam_backend PACKAGE_DIR python/aslam_backend)
install(DIRECTORY include/ DESTINATION include)

ament_export_include_directories(include)
ament_export_dependencies(aslam_backend aslam_backend_expressions numpy_eigen
  sparse_block_matrix sm_common sm_kinematics sm_timing)
ament_package()
