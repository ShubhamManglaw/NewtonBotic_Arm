"""Full chess simulation: Gazebo chess world + arm + controllers + MoveIt + world interface.

  ros2 launch robot_bringup chess_sim.launch.py               # GUI + RViz
  ros2 launch robot_bringup chess_sim.launch.py headless:=true rviz:=false

The world SDF is generated from chess_simulation/config/board.yaml at launch time.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            OpaqueFunction)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _world(context):
    from chess_simulation.board import BoardGeometry
    from chess_simulation.world_gen import world_sdf
    ros_home = os.environ.get('ROS_HOME', os.path.expanduser('~/.ros'))
    os.makedirs(ros_home, exist_ok=True)
    path = os.path.join(ros_home, 'chess_world.sdf')
    with open(path, 'w') as f:
        f.write(world_sdf(BoardGeometry()))
    bringup = get_package_share_directory('robot_bringup')
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'sim_moveit.launch.py')),
        launch_arguments={'world': path,
                          'headless': LaunchConfiguration('headless'),
                          'rviz': LaunchConfiguration('rviz'),
                          'use_gripper': LaunchConfiguration('use_gripper')}.items())]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('use_gripper', default_value='false'),
        OpaqueFunction(function=_world),
        Node(package='ros_gz_bridge', executable='parameter_bridge',
             name='chess_world_bridge', output='screen',
             arguments=['/world/chess_world/set_pose@ros_gz_interfaces/srv/SetEntityPose',
                        '/world/chess_world/create@ros_gz_interfaces/srv/SpawnEntity',
                        '/world/chess_world/remove@ros_gz_interfaces/srv/DeleteEntity']),
        Node(package='chess_simulation', executable='world_interface',
             name='chess_world', output='screen',
             parameters=[{'use_sim_time': True}]),
    ])
