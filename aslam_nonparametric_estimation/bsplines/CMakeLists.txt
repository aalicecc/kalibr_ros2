cmake_minimum_required(VERSION 3.8)
project(bsplines)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_timing REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(Boost REQUIRED COMPONENTS system thread serialization filesystem regex)

add_library(${PROJECT_NAME} 
  src/BSpline.cpp
  src/BSplinePose.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_link_libraries(${PROJECT_NAME}
  sm_common::sm_common sm_timing::sm_timing sm_eigen::sm_eigen
  sm_kinematics::sm_kinematics sparse_block_matrix::sparse_block_matrix
  ${Boost_LIBRARIES})

install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)

install(DIRECTORY include/${PROJECT_NAME}/
  DESTINATION include/${PROJECT_NAME}
)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_export_dependencies(sm_common sm_timing sm_eigen sm_kinematics
  sparse_block_matrix Boost)
ament_package()
