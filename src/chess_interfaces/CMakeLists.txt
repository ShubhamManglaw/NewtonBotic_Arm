cmake_minimum_required(VERSION 3.8)
project(chess_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/PieceMove.msg"
  "msg/PieceState.msg"
  "srv/GetPieceStates.srv"
  "srv/ReplacePiece.srv"
  "srv/SubmitMove.srv"
  "action/ExecuteMoves.action"
  DEPENDENCIES geometry_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
