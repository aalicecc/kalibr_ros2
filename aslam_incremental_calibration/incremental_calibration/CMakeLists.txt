cmake_minimum_required(VERSION 3.8)
project(incremental_calibration)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  system thread serialization filesystem regex)
find_package(TBB REQUIRED)

add_library(${PROJECT_NAME}
  src/base/Serializable.cpp
  src/base/Timestamp.cpp
  src/base/Condition.cpp
  src/base/Mutex.cpp
  src/base/Thread.cpp
  src/base/Threads.cpp
  src/base/Timer.cpp
  src/exceptions/Exception.cpp
  src/exceptions/InvalidOperationException.cpp
  src/exceptions/NullPointerException.cpp
  src/exceptions/SystemException.cpp
  src/statistics/NormalDistribution1v.cpp
  src/statistics/ChiSquareDistribution.cpp
  src/statistics/EstimatorMLNormal1v.cpp
  src/functions/IncompleteGammaPFunction.cpp
  src/functions/IncompleteGammaQFunction.cpp
  src/functions/LogFactorialFunction.cpp
  src/functions/LogGammaFunction.cpp
  src/core/IncrementalEstimator.cpp
  src/core/OptimizationProblem.cpp
  src/core/IncrementalOptimizationProblem.cpp
  src/core/LinearSolver.cpp
  src/core/LinearSolverOptions.cpp
  src/algorithms/marginalize.cpp
  src/algorithms/linalg.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME}
  Boost::system Boost::thread TBB::tbb)
ament_target_dependencies(${PROJECT_NAME} sm_eigen aslam_backend)

install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include ${EIGEN3_INCLUDE_DIRS})
ament_export_dependencies(sm_eigen aslam_backend Eigen3 Boost TBB)
ament_package()
