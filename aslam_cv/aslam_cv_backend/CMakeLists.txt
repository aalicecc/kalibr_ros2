cmake_minimum_required(VERSION 3.8)
project(aslam_cv_backend)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_gtest REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_boost REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(sm_opencv REQUIRED)
find_package(sm_property_tree REQUIRED)
find_package(sm_logging REQUIRED)
find_package(sm_timing REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(aslam_backend_expressions REQUIRED)
find_package(aslam_time REQUIRED)
find_package(aslam_cameras REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(Boost REQUIRED COMPONENTS system thread serialization filesystem regex)
find_package(OpenCV REQUIRED)

add_library(${PROJECT_NAME}
  src/GridCalibrationTargetDesignVariableContainer.cpp
  # src/CameraGeometryDesignVariableContainer.cpp
  # src/NCameraSystemDesignVariableContainer.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${sm_opencv_INCLUDE_DIRS} ${OpenCV_INCLUDE_DIRS} ${Boost_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME}
  aslam_backend::aslam_backend
  aslam_backend_expressions::aslam_backend_expressions
  aslam_cameras::aslam_cameras
  sparse_block_matrix::sparse_block_matrix
  ${OpenCV_LIBRARIES} ${Boost_LIBRARIES})

if(BUILD_TESTING)
  # Avoid clash with tr1::tuple: https://code.google.com/p/googletest/source/browse/trunk/README?r=589#257
  add_definitions(-DGTEST_USE_OWN_TR1_TUPLE=0)

  ament_add_gtest(${PROJECT_NAME}_test
    test/test_main.cpp
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
ament_export_include_directories(include ${OpenCV_INCLUDE_DIRS})
ament_export_dependencies(aslam_backend aslam_backend_expressions
  aslam_cameras sparse_block_matrix OpenCV Boost)
ament_package()
