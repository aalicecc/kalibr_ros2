cmake_minimum_required(VERSION 3.8)
project(aslam_cameras_april)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(sm_python REQUIRED)
find_package(aslam_cameras REQUIRED)
find_package(ethz_apriltag2 REQUIRED)
find_package(numpy_eigen REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_logging REQUIRED)
find_package(sm_boost REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  serialization system thread filesystem regex)
find_package(Eigen3 REQUIRED)

add_library(${PROJECT_NAME} src/GridCalibrationTargetAprilgrid.cpp)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${EIGEN3_INCLUDE_DIRS}
  ${OpenCV_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME}
  ${OpenCV_LIBS} Boost::serialization Boost::system)
ament_target_dependencies(${PROJECT_NAME}
  aslam_cameras ethz_apriltag2 sm_common sm_logging sm_boost sm_eigen)

add_python_export_library(${PROJECT_NAME}_python python/aslam_cameras_april
  src/module.cpp)
target_include_directories(${PROJECT_NAME}_python PRIVATE include)
target_link_libraries(${PROJECT_NAME}_python ${PROJECT_NAME})
ament_target_dependencies(${PROJECT_NAME}_python
  sm_python aslam_cameras ethz_apriltag2 numpy_eigen sm_common sm_logging
  sm_boost sm_eigen)

ament_python_install_package(aslam_cameras_april
  PACKAGE_DIR python/aslam_cameras_april)
install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include ${EIGEN3_INCLUDE_DIRS})
ament_export_dependencies(aslam_cameras ethz_apriltag2 sm_common sm_logging
  sm_boost sm_eigen OpenCV Boost Eigen3)
ament_package()
