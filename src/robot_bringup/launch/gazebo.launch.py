import xacro
import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node


def generate_launch_description():

    pkg_robot_description = get_package_share_directory(
        "robot_description"
    )

    pkg_ros_gz_sim = get_package_share_directory(
        "ros_gz_sim"
    )


    # Gazebo resource path

    pkg_share_parent = os.path.dirname(
        pkg_robot_description
    )


    gz_resource_env = SetEnvironmentVariable(
        "GZ_SIM_RESOURCE_PATH",
        pkg_share_parent
    )


    ign_resource_env = SetEnvironmentVariable(
        "IGN_GAZEBO_RESOURCE_PATH",
        pkg_share_parent
    )


    # Robot description

    xacro_file = os.path.join(
        pkg_robot_description,
        "urdf",
        "robot.urdf.xacro"
    )

    robot_desc = xacro.process_file(xacro_file).toxml()



    # Robot state publisher

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[
            {
                "robot_description": robot_desc,
                "use_sim_time": True,
            }
        ],
    )



    # Gazebo

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                pkg_ros_gz_sim,
                "launch",
                "gz_sim.launch.py",
            )
        ),
        launch_arguments={
            "gz_args": "-r empty.sdf"
        }.items(),
    )



    # Spawn robot

    spawn_robot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-topic",
            "robot_description",
            "-name",
            "NewtonBotic_Arm",
            "-z",
            "0.0",
        ],
        output="screen",
    )



    # Controller spawners
    #
    # IMPORTANT:
    # No --param-file here.
    # gz_ros2_control already loads controllers.yaml


    joint_state_broadcaster_spawner = Node(
    package="controller_manager",
    executable="spawner",
    arguments=[
        "joint_state_broadcaster",
    ],
    output="screen",
)


    arm_controller_spawner = Node(
    package="controller_manager",
    executable="spawner",
    arguments=[
        "arm_controller",
    ],
    output="screen",
)



    load_joint_state_broadcaster = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_robot,
            on_exit=[
                joint_state_broadcaster_spawner
            ],
        )
    )



    load_arm_controller = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[
                arm_controller_spawner
            ],
        )
    )



    # Clock bridge

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"
        ],
        output="screen",
    )



    return LaunchDescription(
        [
            gz_resource_env,
            ign_resource_env,

            bridge,

            robot_state_publisher,

            gazebo,

            spawn_robot,

            load_joint_state_broadcaster,

            load_arm_controller,
        ]
    )