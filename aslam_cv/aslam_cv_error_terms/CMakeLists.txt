cmake_minimum_required(VERSION 3.8)
project(aslam_cv_error_terms)

find_package(ament_cmake REQUIRED)
find_package(sm_logging REQUIRED)
find_package(sm_property_tree REQUIRED)
find_package(sm_opencv REQUIRED)
find_package(sm_kinematics REQUIRED)
find_package(aslam_time REQUIRED)
find_package(aslam_cameras REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(aslam_cv_backend REQUIRED)
find_package(aslam_backend_expressions REQUIRED)
find_package(sm_boost REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(sm_timing REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(aslam_splines REQUIRED)

##################
## Installation ##
##################
install(DIRECTORY include/
  DESTINATION include
)

ament_export_include_directories(include)
ament_export_dependencies(sm_logging sm_property_tree sm_opencv sm_kinematics
  aslam_time aslam_cameras aslam_backend aslam_cv_backend
  aslam_backend_expressions sm_boost sm_eigen sm_timing
  sparse_block_matrix aslam_splines)
ament_package()
