cmake_minimum_required(VERSION 3.8)
project(aslam_cv_serialization)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(aslam_cameras REQUIRED)
find_package(aslam_time REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_boost REQUIRED)
find_package(sm_property_tree REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(sm_opencv REQUIRED)
find_package(sm_logging REQUIRED)
find_package(opencv2_catkin REQUIRED)
find_package(sm_random REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  serialization system thread filesystem regex)

include(autogen_cameras.cmake)

# Camera polymorphic type registrations are static initializers. Keep this as
# a shared library so the linker cannot discard the generated registration
# translation units from a static archive.
add_library(${PROJECT_NAME} SHARED
  ${AUTOGEN_CAMERA_CPP_FILES}
  src/FrameBaseSerialization.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${Boost_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME}
  Boost::serialization Boost::system)
ament_target_dependencies(${PROJECT_NAME}
  aslam_cameras aslam_time sm_common sm_boost sm_property_tree sm_eigen
  sm_kinematics sm_opencv sm_logging opencv2_catkin sm_random)

install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_export_dependencies(aslam_cameras aslam_time sm_common sm_boost
  sm_property_tree sm_eigen sm_kinematics sm_opencv sm_logging opencv2_catkin
  sm_random Boost)
ament_package()
