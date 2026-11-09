cmake_minimum_required(VERSION 3.8)
project(kalibr)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(aslam_cv_python REQUIRED)
find_package(aslam_backend REQUIRED)
find_package(aslam_backend_expressions REQUIRED)
find_package(aslam_backend_python REQUIRED)
find_package(incremental_calibration_python REQUIRED)
find_package(aslam_cameras_april REQUIRED)
find_package(aslam_splines_python REQUIRED)
find_package(numpy_eigen REQUIRED)
find_package(sparse_block_matrix REQUIRED)
find_package(sm_python REQUIRED)
find_package(aslam_cv_backend_python REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  system thread serialization filesystem regex)

add_library(${PROJECT_NAME}_errorterms
  src/EuclideanError.cpp
  src/GyroscopeError.cpp
  src/AccelerometerError.cpp
)
target_include_directories(${PROJECT_NAME}_errorterms PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
ament_target_dependencies(${PROJECT_NAME}_errorterms
  aslam_backend aslam_backend_expressions sparse_block_matrix sm_python)

add_python_export_library(${PROJECT_NAME}_errorterms_python
  python
  src/module.cpp)
target_link_libraries(${PROJECT_NAME}_errorterms_python
  ${PROJECT_NAME}_errorterms)
ament_target_dependencies(${PROJECT_NAME}_errorterms_python
  aslam_backend aslam_backend_expressions aslam_backend_python
  incremental_calibration_python aslam_cameras_april aslam_splines_python
  numpy_eigen sparse_block_matrix sm_python aslam_cv_backend_python)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(${PROJECT_NAME}_test
    test/test_main.cpp
    test/TestErrorTerms.cpp)
  if(TARGET ${PROJECT_NAME}_test)
    target_link_libraries(${PROJECT_NAME}_test
      ${PROJECT_NAME}_errorterms)
  endif()

  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_ros2_bag_reader test/test_ros2_bag_reader.py)
endif()

ament_python_install_package(kalibr_common PACKAGE_DIR python/kalibr_common)
ament_python_install_package(kalibr_camera_calibration
  PACKAGE_DIR python/kalibr_camera_calibration)
ament_python_install_package(kalibr_imu_camera_calibration
  PACKAGE_DIR python/kalibr_imu_camera_calibration)
ament_python_install_package(kalibr_rs_camera_calibration
  PACKAGE_DIR python/kalibr_rs_camera_calibration)
ament_python_install_package(kalibr_errorterms
  PACKAGE_DIR python/kalibr_errorterms)

install(TARGETS ${PROJECT_NAME}_errorterms
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)
install(PROGRAMS
  python/kalibr_bagcreater
  python/kalibr_camera_focus
  python/kalibr_bagextractor
  python/kalibr_camera_validator
  python/kalibr_visualize_calibration
  python/kalibr_calibrate_cameras
  python/kalibr_visualize_distortion
  python/kalibr_calibrate_imu_camera
  python/kalibr_create_target_pdf
  python/kalibr_calibrate_rs_cameras
  DESTINATION lib/${PROJECT_NAME})

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_export_dependencies(aslam_backend aslam_backend_expressions
  sparse_block_matrix sm_python)
ament_package()
