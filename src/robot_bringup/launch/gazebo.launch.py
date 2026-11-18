"""Spawn the HELENE arm + gripper in Gazebo Sim (Harmonic) with ros2_control.

Usage:
  ros2 launch robot_bringup gazebo.launch.py                 # with GUI
  ros2 launch robot_bringup gazebo.launch.py headless:=true  # server only
  ros2 launch robot_bringup gazebo.launch.py world:=/abs/path/world.sdf
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            RegisterEventHandler, SetEnvironmentVariable)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (Command, LaunchConfiguration,
                                  PythonExpression)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_description = get_package_share_directory('robot_description')
    pkg_bringup = get_package_share_directory('robot_bringup')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    headless = LaunchConfiguration('headless')
    world = LaunchConfiguration('world')
    controllers_file = LaunchConfiguration('controllers_file')

    args = [
        DeclareLaunchArgument('headless', default_value='false',
                              description='Run gz server only (no GUI)'),
        DeclareLaunchArgument('world', default_value='empty.sdf',
                              description='SDF world file'),
        DeclareLaunchArgument(
            'controllers_file',
            default_value=os.path.join(pkg_bringup, 'config', 'controllers.yaml')),
        DeclareLaunchArgument('spawn_x', default_value='0.0'),
        DeclareLaunchArgument('spawn_y', default_value='0.0'),
        DeclareLaunchArgument('spawn_z', default_value='0.0'),
    ]

    # Let Gazebo resolve package://helene_description/... mesh URIs.
    resource_path = os.path.dirname(get_package_share_directory('helene_description'))
    env = [
        SetEnvironmentVariable(
            'GZ_SIM_RESOURCE_PATH',
            resource_path + os.pathsep + os.environ.get('GZ_SIM_RESOURCE_PATH', '')),
    ]

    robot_description = ParameterValue(
        Command([
            'xacro ', os.path.join(pkg_description, 'urdf', 'robot.urdf.xacro'),
            ' use_gazebo:=true',
            ' controllers_file:=', controllers_file,
        ]),
        value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description,
                     'use_sim_time': True}],
    )

    gz_args = PythonExpression([
        "'-r -v 2 ' + ('-s ' if '", headless, "' == 'true' else '') + '", world, "'"])
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': gz_args,
                          'on_exit_shutdown': 'true'}.items(),
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description',
                   '-name', 'NewtonBotic_Arm',
                   '-x', LaunchConfiguration('spawn_x'),
                   '-y', LaunchConfiguration('spawn_y'),
                   '-z', LaunchConfiguration('spawn_z')],
        output='screen',
    )

    def spawner(name):
        return Node(package='controller_manager', executable='spawner',
                    arguments=[name, '--controller-manager-timeout', '60'],
                    output='screen')

    jsb = spawner('joint_state_broadcaster')
    arm = spawner('arm_controller')
    gripper = spawner('gripper_controller')

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen',
    )

    return LaunchDescription(args + env + [
        bridge,
        robot_state_publisher,
        gazebo,
        spawn_robot,
        RegisterEventHandler(OnProcessExit(target_action=spawn_robot,
                                           on_exit=[jsb])),
        RegisterEventHandler(OnProcessExit(target_action=jsb,
                                           on_exit=[arm, gripper])),
    ])
