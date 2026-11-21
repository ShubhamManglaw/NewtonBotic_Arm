"""Everything: Gazebo chess world + arm + MoveIt + manipulation server + game node.

  ros2 launch robot_bringup chess_game.launch.py
  ros2 launch robot_bringup chess_game.launch.py headless:=true rviz:=false
  # then, in another terminal:
  ros2 run chess_game play

startup_demo:=true (default): once the stack is ready, wait demo_delay seconds, then
pick-and-place demo_move (default e2e4) with the real gripper and, if demo_return,
carry the piece back so the board is in the start position again.

execution_mode:=gripper (default) grasps pieces by friction with the real gripper.
execution_mode:=teleport is a TEST MODE: arm motions are real but pieces are moved
by Gazebo set_pose (useful to debug game flow independently of grasping).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription,
                            TimerAction)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup = get_package_share_directory('robot_bringup')
    manip_cfg = os.path.join(get_package_share_directory('chess_manipulation'),
                             'config', 'manipulation.yaml')
    game_cfg = os.path.join(get_package_share_directory('chess_game'), 'config', 'game.yaml')
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'chess_sim.launch.py')),
        launch_arguments={k: LaunchConfiguration(k)
                          for k in ('headless', 'rviz')}.items())
    manip = Node(package='chess_manipulation', executable='manipulation_server',
                 name='chess_manipulation', output='screen',
                 parameters=[manip_cfg, {'use_sim_time': True,
                                         'execution_mode': LaunchConfiguration('execution_mode')}])
    game = Node(package='chess_game', executable='game_node', name='chess_game',
                output='screen', parameters=[game_cfg, {'use_sim_time': True}])
    demo = Node(package='chess_manipulation', executable='startup_demo', name='startup_demo',
                output='screen', condition=IfCondition(LaunchConfiguration('startup_demo')),
                parameters=[{'delay': LaunchConfiguration('demo_delay'),
                             'move': LaunchConfiguration('demo_move'),
                             'return_piece': LaunchConfiguration('demo_return')}])
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('startup_demo', default_value='true',
                              description='pick-and-place demo shortly after startup'),
        DeclareLaunchArgument('demo_delay', default_value='5.0',
                              description='seconds after the stack is ready'),
        DeclareLaunchArgument('demo_move', default_value='e2e4'),
        DeclareLaunchArgument('demo_return', default_value='true',
                              description='carry the piece back afterwards'),
        DeclareLaunchArgument('execution_mode', default_value='gripper',
                              description="'gripper' or 'teleport' (TEST ONLY)"),
        sim,
        TimerAction(period=15.0, actions=[manip, game, demo]),
    ])
