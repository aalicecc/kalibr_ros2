cmake_minimum_required(VERSION 3.8)
project(numpy_eigen)

set(CMAKE_CXX_STANDARD 14)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(python_module REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(Boost REQUIRED COMPONENTS python310)
find_package(Python3 REQUIRED COMPONENTS Development.Module NumPy)

include(src/autogen_files.cmake)
add_python_export_library(${PROJECT_NAME}
  "${CMAKE_CURRENT_SOURCE_DIR}/python/${PROJECT_NAME}"
  ${AUTOGEN_FILES})
target_include_directories(${PROJECT_NAME} PRIVATE
  include
  "${CMAKE_CURRENT_SOURCE_DIR}/include/${PROJECT_NAME}"
  ${EIGEN3_INCLUDE_DIRS}
  ${Python3_NumPy_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME} Boost::python310)
target_compile_definitions(${PROJECT_NAME} PRIVATE __STRICT_ANSI__)
target_compile_options(${PROJECT_NAME} PRIVATE -fpermissive)

include(src/autogen_test_files.cmake)
add_python_export_library(${PROJECT_NAME}_test
  "${CMAKE_CURRENT_SOURCE_DIR}/python/${PROJECT_NAME}"
  ${AUTOGEN_TEST_FILES})
target_include_directories(${PROJECT_NAME}_test PRIVATE
  include
  "${CMAKE_CURRENT_SOURCE_DIR}/include/${PROJECT_NAME}"
  ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME}_test Boost::python310)
target_compile_options(${PROJECT_NAME}_test PRIVATE -fpermissive)

ament_python_install_package(${PROJECT_NAME} PACKAGE_DIR src/${PROJECT_NAME})
install(DIRECTORY include/${PROJECT_NAME}/ DESTINATION include/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_${PROJECT_NAME} test/numpy_eigen_tests.py)
endif()

ament_export_include_directories(include)
ament_export_dependencies(Eigen3)
ament_package()
