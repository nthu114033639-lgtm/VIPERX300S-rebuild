#!/usr/bin/env python3
from copy import deepcopy
from pathlib import Path
import os
import sys

import rclpy
from rclpy.node import Node
from rclpy.logging import get_logger
from threading import Thread
from tf2_ros import Buffer, TransformListener

from geometry_msgs.msg import PoseStamped

SCRIPT_DIR = Path(__file__).resolve().parent
VLSERVO_SRC = SCRIPT_DIR / "ros2_ws" / "src" / "vlservo"
if VLSERVO_SRC.is_dir() and str(VLSERVO_SRC) not in sys.path:
    sys.path.insert(0, str(VLSERVO_SRC))

from VLServo.moveit_marker_bridge import MoveItMarkerBridge

class MoveItPlanner:
    def __init__(self):
        self._logger = get_logger("moveit_planner")
        self.moveit_bridge = MoveItMarkerBridge(
            robot_name="vx300s",
            planning_group="interbotix_arm",
            eef_link="vx300s/ee_gripper_link",
            joint_order=["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate"],
            target_frame="vx300s/base_link",
            camera_frame="camera_link",
            velocity_scaling=0.2,
            acceleration_scaling=0.2,
        )
        self._logger.info("✅ MoveIt bridge 已啟動！")

    def plan_and_execute(self, pose_goal: PoseStamped, velocity_scaling=0.1, acceleration_scaling=0.1):
        self._logger.info(f"🚀 正在規劃路徑至: X:{pose_goal.pose.position.x:.3f}, Y:{pose_goal.pose.position.y:.3f}, Z:{pose_goal.pose.position.z:.3f}")

        self.moveit_bridge.velocity_scaling = float(velocity_scaling)
        self.moveit_bridge.acceleration_scaling = float(acceleration_scaling)

        ik_response = self.moveit_bridge._compute_ik(pose_goal)
        if ik_response is None:
            self._logger.error("IK service unavailable")
            return False
        if ik_response.error_code.val != 1:
            self._logger.error(f"IK failure (code {ik_response.error_code.val})")
            return False

        joint_positions = self.moveit_bridge._build_joint_vector(ik_response.solution.joint_state)
        if joint_positions is None:
            self._logger.error("IK response missing required joints")
            return False

        self.moveit_bridge._last_joint_positions = list(joint_positions)
        self.moveit_bridge._last_pose_target = pose_goal

        result = self.moveit_bridge._send_move_group_goal(joint_positions, plan_only=False)
        if result.success:
            self._logger.info("✅ 執行成功")
            return True

        self._logger.error(f"規劃/執行失敗：{result.message}")
        return False

    def go_to_home_pose(self):
        self._logger.info("🏠 回到 Home 姿勢...")
        result = self.moveit_bridge._send_move_group_goal([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], plan_only=False)
        if not result.success:
            self._logger.error(f"回 Home 失敗：{result.message}")

    def destroy(self):
        self.moveit_bridge.destroy()

def main(args=None):
    moveit_planner = MoveItPlanner()
    node = Node("pick_and_place_controller")
    executor_thread = Thread(target=rclpy.spin, args=[node], daemon=True)
    executor_thread.start()

    # TF 監聽器
    tf_buffer = Buffer()
    tf_listener = TransformListener(tf_buffer, node, spin_thread=False)

    # 從指令列讀取目標
    if len(sys.argv) > 1:
        target_object = sys.argv[1].lower()
    else:
        target_object = 'bottle'

    target_frame_name = f'target_{target_object}'
    node.get_logger().info(f"🎯 設定抓取目標為: '{target_object}'")
    node.get_logger().info(f"⏳ 等待 YOLO 辨識出目標 ({target_frame_name})...")

    target_found = False
    while rclpy.ok() and not target_found:
        try:
            trans = tf_buffer.lookup_transform('vx300s/base_link', target_frame_name, rclpy.time.Time())
            target_found = True
        except Exception as e:
            node.get_logger().info(f"⏳ 正在搜尋 '{target_frame_name}' TF... ({e})", throttle_duration_sec=2.0)
            rclpy.spin_once(node, timeout_sec=0.5)

    if target_found and trans:
        x = trans.transform.translation.x
        y = trans.transform.translation.y
        z = trans.transform.translation.z
        node.get_logger().info(f"✅ 發現目標！座標: X:{x:.3f}, Y:{y:.3f}, Z:{z:.3f} m")

        if x < 0.15 or x > 0.65 or y < -0.40 or y > 0.40 or z < -0.05:
            node.get_logger().error("🛑 [安全防護攔截] 目標座標超出合理工作範圍！任務強制取消。")
            rclpy.shutdown()
            return

        user_input = input("\n⚠️ 座標確認完畢！請確認周遭安全，按 [Enter] 開始執行抓取，或輸入 [q] 取消: ")
        if user_input.lower() == 'q':
            node.get_logger().info("🚫 使用者手動取消任務。")
            rclpy.shutdown()
            return

        # 建立目標姿態
        pre_grasp_pose = PoseStamped()
        pre_grasp_pose.header.frame_id = "vx300s/base_link"
        pre_grasp_pose.pose.position.x = x
        pre_grasp_pose.pose.position.y = y
        pre_grasp_pose.pose.position.z = z + 0.10  # 預備點
        pre_grasp_pose.pose.orientation.x = 0.0
        pre_grasp_pose.pose.orientation.y = 0.707
        pre_grasp_pose.pose.orientation.z = 0.0
        pre_grasp_pose.pose.orientation.w = 0.707  # 夾爪垂直朝下 (pitch=1.57)

        grasp_pose = PoseStamped()
        grasp_pose.header.frame_id = "vx300s/base_link"
        grasp_pose.pose = deepcopy(pre_grasp_pose.pose)
        grasp_pose.pose.position.z = z + 0.015 # 抓取點

        # 執行動作序列
        if moveit_planner.plan_and_execute(pre_grasp_pose, velocity_scaling=0.2):
            if moveit_planner.plan_and_execute(grasp_pose, velocity_scaling=0.1): # 下降時更慢
                # 夾取邏輯 (目前註解)
                # node.get_logger().info("✊ 閉合夾爪...")
                # time.sleep(1.0)
                if moveit_planner.plan_and_execute(pre_grasp_pose, velocity_scaling=0.2): # 抬起
                    moveit_planner.go_to_home_pose()

    moveit_planner.destroy()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()