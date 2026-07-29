from launch import LaunchDescription
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

import os
import xacro
def generate_launch_description():
    package_path=get_package_share_directory("robot_description")
    xacro_file_path=os.path.join(package_path,"urdf","robot.urdf.xacro")
    xml=xacro.parse(open(xacro_file_path))
    xacro.process_doc(xml)
    robot_description_content=xml.toxml()
    rviz_config = os.path.join(package_path, "rviz", "robot.rviz")
    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{'robot_description': robot_description_content}],
        ),
        Node(
            package="joint_state_publisher_gui",
            executable="joint_state_publisher_gui",
            name="joint_state_publisher_gui",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            arguments=["-d", rviz_config],
            
        )
    ])