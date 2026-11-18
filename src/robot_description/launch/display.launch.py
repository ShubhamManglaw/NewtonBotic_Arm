"""Visualise the arm in RViz with joint sliders (no simulation)."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_share = get_package_share_directory('robot_description')

    robot_description = ParameterValue(
        Command(['xacro ', os.path.join(pkg_share, 'urdf', 'robot.urdf.xacro'),
                 ' use_gazebo:=false use_gripper:=',
                 LaunchConfiguration('use_gripper')]),
        value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument('use_gripper', default_value='false'),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             output='screen',
             parameters=[{'robot_description': robot_description}]),
        Node(package='joint_state_publisher_gui',
             executable='joint_state_publisher_gui', output='screen'),
        Node(package='rviz2', executable='rviz2', name='rviz2', output='screen',
             arguments=['-d', os.path.join(pkg_share, 'rviz', 'robot.rviz')]),
    ])
