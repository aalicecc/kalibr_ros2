cmake_minimum_required(VERSION 3.8)
project(aslam_cv_python)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(sm_python REQUIRED)
find_package(sm_opencv REQUIRED)
find_package(opencv2_catkin REQUIRED)
find_package(aslam_cv_serialization REQUIRED)
find_package(aslam_imgproc REQUIRED)
find_package(aslam_cameras REQUIRED)
find_package(aslam_time REQUIRED)
find_package(OpenCV REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  serialization system thread filesystem regex)

add_python_export_library(${PROJECT_NAME} python/aslam_cv
  src/module.cpp
  src/CameraGeometries.cpp
  src/CameraGeometry.cpp
  src/Time.cpp
  src/Frontend.cpp
  src/Frame.cpp
  src/CameraProjections.cpp
  src/CameraShutters.cpp
  src/GridCalibration.cpp
  src/Undistorters.cpp
  src/OmniUndistorter.cpp
  src/PinholeUndistorter.cpp
)
target_include_directories(${PROJECT_NAME} PRIVATE include ${OpenCV_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME} Boost::serialization ${OpenCV_LIBS})
target_compile_options(${PROJECT_NAME} PRIVATE -Wno-deprecated-copy)
ament_target_dependencies(${PROJECT_NAME}
  sm_common sm_eigen sm_kinematics sm_python sm_opencv opencv2_catkin
  aslam_cv_serialization aslam_imgproc aslam_cameras aslam_time)

ament_python_install_package(aslam_cv PACKAGE_DIR python/aslam_cv)
install(DIRECTORY include/ DESTINATION include)

ament_export_include_directories(include)
ament_export_dependencies(sm_common sm_eigen sm_kinematics sm_python sm_opencv
  opencv2_catkin aslam_cv_serialization aslam_imgproc aslam_cameras aslam_time
  OpenCV Boost)
ament_package()
