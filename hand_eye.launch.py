from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    """
    啟動一個靜態 TF 發布節點，用來廣播手眼校正後得到的
    手臂末端 (ee_gripper_link) 到 相機根目錄 (camera_link) 的轉換矩陣。
    """
    return LaunchDescription([
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='hand_eye_static_tf_publisher',
            arguments=[
                # ros2 run tf2_ros static_transform_publisher x y z qx qy qz qw frame_id child_frame_id
                '-0.06156', '0.01058', '0.05294',
                '0.07425', '0.06706', '0.02969', '0.99454',
                'vx300s/ee_gripper_link',
                'camera_link'
            ],
        )
    ])