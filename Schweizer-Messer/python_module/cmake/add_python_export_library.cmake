function(add_python_export_library target_name python_module_directory)
  find_package(Python3 REQUIRED COMPONENTS Development.Module NumPy)
  find_package(Boost REQUIRED COMPONENTS python310)
  find_package(ament_cmake_python REQUIRED)

  # Boost.Python modules in this source tree use the conventional `lib` prefix.
  add_library(${target_name} MODULE ${ARGN})
  set_target_properties(${target_name} PROPERTIES
    PREFIX "lib"
    SUFFIX ".so"
    POSITION_INDEPENDENT_CODE ON
  )
  target_include_directories(${target_name} PRIVATE
    ${Python3_NumPy_INCLUDE_DIRS})
  target_link_libraries(${target_name} Python3::Module Boost::python310)

  get_filename_component(_module_directory
    "${python_module_directory}" ABSOLUTE
    BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
  get_filename_component(_package_directory "${_module_directory}" NAME)
  if(_package_directory STREQUAL "python")
    set(_package_directory "")
  endif()

  ament_get_python_install_dir(_python_install_directory)
  install(TARGETS ${target_name}
    LIBRARY DESTINATION "${_python_install_directory}/${_package_directory}")
endfunction()
