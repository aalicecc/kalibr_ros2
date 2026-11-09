cmake_minimum_required(VERSION 3.8)
project(aslam_imgproc)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(sm_random REQUIRED)
find_package(sm_boost REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(sm_opencv REQUIRED)
find_package(sm_logging REQUIRED)
find_package(sm_property_tree REQUIRED)
find_package(aslam_time REQUIRED)
find_package(aslam_cameras REQUIRED)
find_package(opencv2_catkin REQUIRED)
find_package(numpy_eigen REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  system thread serialization filesystem regex)

add_library(${PROJECT_NAME} src/UndistorterBase.cpp)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_options(${PROJECT_NAME} PRIVATE
  -Wno-deprecated-copy -Wno-maybe-uninitialized)
target_link_libraries(${PROJECT_NAME} Boost::system)
ament_target_dependencies(${PROJECT_NAME}
  sm_common sm_eigen sm_random sm_boost sm_kinematics sm_opencv sm_logging
  sm_property_tree aslam_time aslam_cameras opencv2_catkin numpy_eigen)

install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_export_dependencies(sm_common sm_eigen sm_random sm_boost sm_kinematics
  sm_opencv sm_logging sm_property_tree aslam_time aslam_cameras
  opencv2_catkin numpy_eigen Boost)
ament_package()
