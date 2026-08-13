cmake_minimum_required(VERSION 3.8)
project(robot_description)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find build system
find_package(ament_cmake REQUIRED)

# Install URDF/Xacro files
install(
  DIRECTORY urdf
  DESTINATION share/${PROJECT_NAME}
)

# Install meshes
install(
  DIRECTORY meshes
  DESTINATION share/${PROJECT_NAME}
)

# Install launch files
install(
  DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

# Install RViz configuration
install(
  DIRECTORY rviz
  DESTINATION share/${PROJECT_NAME}
)

# Install configuration files
install(
  DIRECTORY config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()