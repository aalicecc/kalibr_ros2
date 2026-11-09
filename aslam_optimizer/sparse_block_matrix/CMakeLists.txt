cmake_minimum_required(VERSION 3.8)
project(sparse_block_matrix)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_gtest REQUIRED)
find_package(sm_common REQUIRED)
find_package(sm_eigen REQUIRED)
find_package(TBB REQUIRED)
find_package(Boost REQUIRED COMPONENTS system serialization)

list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR}/cmake)
find_package(SuiteSparse REQUIRED)

find_package(Eigen3)

include_directories(
  include
  ${CHOLMOD_INCLUDE_DIR}
  ${EIGEN3_INCLUDE_DIRS}
)

add_library(${PROJECT_NAME}
  src/matrix_structure.cpp
  src/sparse_helper.cpp
  src/marginal_covariance_cholesky.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${CHOLMOD_INCLUDE_DIR}
  ${EIGEN3_INCLUDE_DIRS}
  ${Boost_INCLUDE_DIRS})
target_link_libraries(${PROJECT_NAME}
  sm_common::sm_common sm_eigen::sm_eigen
  ${TBB_LIBRARIES} ${SUITESPARSE_LIBRARIES} ${Boost_LIBRARIES})

if(BUILD_TESTING)
  # Avoid clash with tr1::tuple: https://code.google.com/p/googletest/source/browse/trunk/README?r=589#257
  add_definitions(-DGTEST_USE_OWN_TR1_TUPLE=0)

  ament_add_gtest(${PROJECT_NAME}_tests
    test/test_main.cpp
    test/solver_tests.cpp
    test/sparse_block_matrix_tests.cpp
  )
  target_link_libraries(${PROJECT_NAME}_tests ${PROJECT_NAME} ${TBB_LIBRARIES} ${SUITESPARSE_LIBRARIES})
endif()

# Install
install(TARGETS ${PROJECT_NAME} EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)
install(DIRECTORY include/${PROJECT_NAME}/ DESTINATION include/${PROJECT_NAME})
install(FILES cmake/FindSuiteSparse.cmake DESTINATION share/${PROJECT_NAME}/cmake)

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_include_directories(include ${CHOLMOD_INCLUDE_DIR} ${EIGEN3_INCLUDE_DIRS})
ament_export_dependencies(sm_common sm_eigen Boost)
ament_package()
