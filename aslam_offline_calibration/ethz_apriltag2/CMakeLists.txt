cmake_minimum_required(VERSION 3.8)
project(ethz_apriltag2)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(OpenCV REQUIRED)

file(GLOB SOURCE_FILES CONFIGURE_DEPENDS "src/*.cc")
add_library(${PROJECT_NAME} ${SOURCE_FILES})
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${EIGEN3_INCLUDE_DIRS}
  ${OpenCV_INCLUDE_DIRS})
target_compile_options(${PROJECT_NAME} PRIVATE -O3)
target_link_libraries(${PROJECT_NAME} PRIVATE ${OpenCV_LIBS})

option(ETHZ_APRILTAG_BUILD_DEMO
  "Build the optional V4L2 camera capture demo"
  OFF)

if(ETHZ_APRILTAG_BUILD_DEMO AND NOT APPLE)
  find_path(V4L2_INCLUDE_DIR libv4l2.h)
  find_library(V4L2_LIBRARY v4l2)
  if(NOT V4L2_INCLUDE_DIR OR NOT V4L2_LIBRARY)
    message(FATAL_ERROR
      "ETHZ_APRILTAG_BUILD_DEMO requires libv4l-dev")
  endif()

  add_executable(apriltags_demo
    src/example/apriltags_demo.cpp
    src/example/Serial.cpp)
  target_include_directories(apriltags_demo PRIVATE ${V4L2_INCLUDE_DIR})
  target_link_libraries(apriltags_demo PRIVATE ${PROJECT_NAME} ${V4L2_LIBRARY})
endif()

install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
if(TARGET apriltags_demo)
  install(TARGETS apriltags_demo DESTINATION lib/${PROJECT_NAME})
endif()
install(DIRECTORY include/ DESTINATION include)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include ${EIGEN3_INCLUDE_DIRS})
ament_export_dependencies(Eigen3 OpenCV)
ament_package()
