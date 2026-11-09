cmake_minimum_required(VERSION 3.8)
project(opencv2_catkin)

find_package(ament_cmake REQUIRED)
find_package(OpenCV REQUIRED)

ament_export_include_directories(${OpenCV_INCLUDE_DIRS})
ament_export_libraries(${OpenCV_LIBRARIES})
ament_package()
