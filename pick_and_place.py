#!/usr/bin/env python3
from copy import deepcopy
from pathlib import Path
import os
import sys
import time

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

    def go_to_joint_positions(self, joints, label="目標位置"):
        self._logger.info(f"🔄 移動至 {label}...")
        result = self.moveit_bridge._send_move_group_goal(joints, plan_only=False)
        if result.success:
            self._logger.info(f"✅ 已到達 {label}")
            return True
        self._logger.error(f"移動至 {label} 失敗：{result.message}")
        return False

    def go_to_home_pose(self):
        # 轉正姿勢
        return self.go_to_joint_positions([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "Home 姿勢 (轉正)")

    def go_to_sleep_pose(self):
        # 💡 這裡改成你剛才提供、實際讀取出來的精準安全 Sleep 座標！
        sleep_joints = [0.0046, -1.6153, 1.5509, -0.0015, 0.2654, -0.0015]
        return self.go_to_joint_positions(sleep_joints, "自訂 Sleep 姿勢 (精準收合)")

    def destroy(self):
        if hasattr(self.moveit_bridge, 'destroy'):
            self.moveit_bridge.destroy()

def main(args=None):
    moveit_planner = MoveItPlanner()
    node = Node("pick_and_place_controller")

    # 使用背景執行緒 spin 節點
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
    trans = None
    while rclpy.ok() and not target_found:
        try:
            trans = tf_buffer.lookup_transform('vx300s/base_link', target_frame_name, rclpy.time.Time())
            target_found = True
        except Exception as e:
            node.get_logger().info(f"⏳ 正在搜尋 '{target_frame_name}' TF... ({e})", throttle_duration_sec=2.0)
            time.sleep(0.5)

    if target_found and trans:
        x = trans.transform.translation.x
        y = trans.transform.translation.y
        z = trans.transform.translation.z
        node.get_logger().info(f"✅ 發現目標！座標: X:{x:.3f}, Y:{y:.3f}, Z:{z:.3f} m")

        if x < 0.15 or x > 0.65 or y < -0.40 or y > 0.40 or z < -0.05:
            node.get_logger().error("🛑 [安全防護攔截] 目標座標超出合理工作範圍！任務強制取消。")
        else:
            user_input = input("\n⚠️ 座標確認完畢！請確認周遭安全，按 [Enter] 開始執行抓取，或輸入 [q] 取消: ")
            if user_input.lower() == 'q':
                node.get_logger().info("🚫 使用者手動取消任務。")
            else:
                # 建立目標姿態
                pre_grasp_pose = PoseStamped()
                pre_grasp_pose.header.frame_id = "vx300s/base_link"
                pre_grasp_pose.pose.position.x = x
                pre_grasp_pose.pose.position.y = y
                pre_grasp_pose.pose.position.z = z + 0.10  # 預備點
                pre_grasp_pose.pose.orientation.x = 0.0
                pre_grasp_pose.pose.orientation.y = 0.707
                pre_grasp_pose.pose.orientation.z = 0.0
                pre_grasp_pose.pose.orientation.w = 0.707

                grasp_pose = PoseStamped()
                grasp_pose.header.frame_id = "vx300s/base_link"
                grasp_pose.pose = deepcopy(pre_grasp_pose.pose)
                grasp_pose.pose.position.z = z + 0.015 # 抓取點

                # 🚀 執行動作序列
                if moveit_planner.plan_and_execute(pre_grasp_pose, velocity_scaling=0.2):
                    if moveit_planner.plan_and_execute(grasp_pose, velocity_scaling=0.1): 
                        node.get_logger().info("✊ [模擬] 閉合夾爪...")
                        time.sleep(1.0)
                        
                        if moveit_planner.plan_and_execute(pre_grasp_pose, velocity_scaling=0.2): # 抬起
                            
                            # 💡 兩段式安全回家流程：先轉正，再回你指定的精準 Sleep 姿勢
                            node.get_logger().info("🛹 準備回程，執行安全緩衝動作...")
                            moveit_planner.go_to_home_pose()   # 1. 先轉正直立
                            time.sleep(0.5)
                            moveit_planner.go_to_sleep_pose()  # 2. 再安全收折到精準 Sleep 位置

    # 🏁 安全清理並退出
    node.get_logger().info("👋 正在關閉系統...")
    
    if 'tf_listener' in locals():
        del tf_listener
        
    moveit_planner.destroy()
    node.destroy_node()
    
    rclpy.shutdown()
    executor_thread.join(timeout=1.0)
    print("🏁 任務完成，程式已安全結束。")

if __name__ == "__main__":
    from rclpy.executors import ExternalShutdownException
    
    try:
        main()
    except ExternalShutdownException:
        # 💡 完美攔截並吃掉結束時的背景執行緒斷電錯誤
        pass
    except KeyboardInterrupt:
        print("\n🛑 使用者強制中斷程式。")