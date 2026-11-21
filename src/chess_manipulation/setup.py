from glob import glob

from setuptools import find_packages, setup

package_name = 'chess_manipulation'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Shubham',
    maintainer_email='Shubhammanglaw@gmail.com',
    description='Pick-and-place primitives for chess pieces using MoveIt 2.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'reachability = chess_manipulation.reachability:main',
            'motion_check = chess_manipulation.motion_check:main',
            'startup_demo = chess_manipulation.startup_demo:main',
            'manipulation_server = chess_manipulation.manipulation_server:main',
        ],
    },
)
