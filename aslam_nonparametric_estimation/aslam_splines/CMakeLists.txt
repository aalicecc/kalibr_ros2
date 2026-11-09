cmake_minimum_required(VERSION 3.8)
project(aslam_splines)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_gtest REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(aslam_backend_expressions REQUIRED)
find_package(bsplines REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(sm_timing REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(Boost REQUIRED COMPONENTS system thread serialization filesystem regex)

add_library(${PROJECT_NAME}
  src/BSplinePoseDesignVariable.cpp
  src/BSplineExpressions.cpp
  src/EuclideanBSplineDesignVariable.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${EIGEN3_INCLUDE_DIRS} ${Boost_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME}
  aslam_backend::aslam_backend
  aslam_backend_expressions::aslam_backend_expressions
  bsplines::bsplines sparse_block_matrix::sparse_block_matrix
  sm_common::sm_common sm_kinematics::sm_kinematics sm_timing::sm_timing
  ${Boost_LIBRARIES})

if(BUILD_TESTING)
  ament_add_gtest(${PROJECT_NAME}_test
    test/test_main.cpp
    test/TestBSplineExpressions.cpp
    test/TestErrors.cpp
    #  test/TestOPTBSpline.cpp
    )
  target_link_libraries(${PROJECT_NAME}_test ${PROJECT_NAME})
endif()

##################
## Installation ##
##################
install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)

## Mark cpp header files for installation
install(DIRECTORY include/
  DESTINATION include
)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include ${EIGEN3_INCLUDE_DIRS})
ament_export_dependencies(aslam_backend aslam_backend_expressions bsplines
  sparse_block_matrix sm_common sm_kinematics sm_timing Eigen3 Boost)
ament_package()
