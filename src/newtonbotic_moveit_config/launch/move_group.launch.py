"""Start move_group (and optionally RViz) for the HELENE arm.

Assumes the controllers are already running (e.g. robot_bringup gazebo.launch.py).
"""
import os
import sys

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moveit_config  # noqa: E402


def _setup(context):
    use_sim_time = LaunchConfiguration('use_sim_time').perform(context) == 'true'
    cfg = moveit_config.build()
    sim = {'use_sim_time': use_sim_time}

    move_group = Node(
        package='moveit_ros_move_group', executable='move_group', output='screen',
        parameters=[cfg.to_dict(), sim,
                    {'trajectory_execution.allowed_start_tolerance': 0.05,
                     'publish_planning_scene_hz': 10.0}],
    )
    rviz = Node(
        package='rviz2', executable='rviz2', output='log',
        arguments=['-d', os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'moveit.rviz')],
        parameters=[cfg.robot_description, cfg.robot_description_semantic,
                    cfg.robot_description_kinematics, cfg.planning_pipelines,
                    cfg.joint_limits, sim],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )
    return [move_group, rviz]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='false'),
        OpaqueFunction(function=_setup),
    ])
