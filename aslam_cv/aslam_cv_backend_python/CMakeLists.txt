cmake_minimum_required(VERSION 3.8)
project(aslam_cv_backend_python)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_python REQUIRED)
find_package(sm_opencv REQUIRED)
find_package(numpy_eigen REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(aslam_backend_expressions REQUIRED)
find_package(aslam_backend_python REQUIRED)
find_package(opencv2_catkin REQUIRED)
find_package(aslam_cameras REQUIRED)
find_package(aslam_cv_error_terms REQUIRED)
find_package(aslam_splines REQUIRED)
find_package(aslam_cv_python REQUIRED)
find_package(aslam_cv_backend REQUIRED)
find_package(aslam_time REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  system thread serialization filesystem regex)

add_python_export_library(${PROJECT_NAME} python/aslam_cv_backend
  src/module.cpp
  src/GridCalibration.cpp
)
target_include_directories(${PROJECT_NAME} PRIVATE include)
ament_target_dependencies(${PROJECT_NAME}
  sm_common sm_python sm_opencv numpy_eigen sparse_block_matrix
  aslam_backend aslam_backend_expressions aslam_backend_python
  opencv2_catkin aslam_cameras aslam_cv_error_terms aslam_splines
  aslam_cv_python aslam_cv_backend aslam_time)

ament_python_install_package(aslam_cv_backend PACKAGE_DIR python/aslam_cv_backend)
install(DIRECTORY include/ DESTINATION include)

ament_export_include_directories(include)
ament_export_dependencies(sm_common sm_python sm_opencv numpy_eigen
  sparse_block_matrix aslam_backend aslam_backend_expressions
  aslam_backend_python opencv2_catkin aslam_cameras aslam_cv_error_terms
  aslam_splines aslam_cv_python aslam_cv_backend aslam_time)
ament_package()
