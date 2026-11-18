"""Gazebo + ros2_control + MoveIt in one command.

  ros2 launch robot_bringup sim_moveit.launch.py headless:=true rviz:=false
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            TimerAction)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bringup = get_package_share_directory('robot_bringup')
    moveit = get_package_share_directory('newtonbotic_moveit_config')
    names = ['headless', 'world', 'use_gripper', 'rviz']
    defaults = ['false', 'empty.sdf', 'false', 'true']
    args = [DeclareLaunchArgument(n, default_value=d) for n, d in zip(names, defaults)]
    cfg = {n: LaunchConfiguration(n) for n in names}

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'gazebo.launch.py')),
        launch_arguments={k: cfg[k] for k in ('headless', 'world', 'use_gripper')}.items())
    move_group = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(moveit, 'launch', 'move_group.launch.py')),
        launch_arguments={'use_sim_time': 'true', 'use_gripper': cfg['use_gripper'],
                          'rviz': cfg['rviz']}.items())
    # Give Gazebo / controllers a head start so MoveIt sees joint states at startup.
    return LaunchDescription(args + [gazebo, TimerAction(period=8.0, actions=[move_group])])
