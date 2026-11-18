from glob import glob

from setuptools import find_packages, setup

package_name = 'chess_simulation'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
        ('share/' + package_name + '/worlds', glob('worlds/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Shubham',
    maintainer_email='Shubhammanglaw@gmail.com',
    description='Chessboard and piece geometry, world generation, spawn/reset.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'generate_world = chess_simulation.world_gen:main',
            'world_interface = chess_simulation.world_interface:main',
        ],
    },
)
