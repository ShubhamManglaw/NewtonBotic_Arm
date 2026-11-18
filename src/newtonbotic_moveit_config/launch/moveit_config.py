"""Shared MoveItConfigsBuilder for the HELENE arm (imported by launch files)."""
import os

from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder


def build(use_gazebo='true'):
    xacro = os.path.join(get_package_share_directory('robot_description'),
                         'urdf', 'robot.urdf.xacro')
    return (
        MoveItConfigsBuilder('helene',
                             package_name='newtonbotic_moveit_config')
        .robot_description(file_path=xacro,
                           mappings={'use_gazebo': use_gazebo})
        .robot_description_semantic(file_path='config/helene.srdf')
        .robot_description_kinematics(file_path='config/kinematics.yaml')
        .joint_limits(file_path='config/joint_limits.yaml')
        .trajectory_execution(file_path='config/moveit_controllers.yaml')
        .pilz_cartesian_limits(file_path='config/pilz_cartesian_limits.yaml')
        .planning_pipelines(pipelines=['ompl', 'pilz_industrial_motion_planner'],
                            default_planning_pipeline='ompl')
        .planning_scene_monitor(publish_robot_description=True,
                                publish_robot_description_semantic=True)
        .to_moveit_configs()
    )
