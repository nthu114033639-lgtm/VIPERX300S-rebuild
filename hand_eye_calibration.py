#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R
import threading
import sys

class HandEyeCalibrator(Node):
    def __init__(self):
        super().__init__('hand_eye_calibrator')
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.R_gripper2base = []
        self.t_gripper2base = []
        self.R_target2cam = []
        self.t_target2cam = []

    def get_transform(self, target_frame, source_frame):
        try:
            # 取得最新的座標轉換
            trans = self.tf_buffer.lookup_transform(target_frame, source_frame, rclpy.time.Time())
            t = [trans.transform.translation.x, trans.transform.translation.y, trans.transform.translation.z]
            q = [trans.transform.rotation.x, trans.transform.rotation.y, trans.transform.rotation.z, trans.transform.rotation.w]
            return np.array(t).reshape(3, 1), R.from_quat(q).as_matrix()
        except Exception as ex:
            self.get_logger().error(f'擷取失敗 (找不到 {source_frame}): {ex}')
            return None, None

    def sample(self):
        # 取得 手臂底座 -> 夾爪末端 的座標
        t_base_ee, R_base_ee = self.get_transform('vx300s/base_link', 'vx300s/ee_gripper_link')
        # 取得 相機鏡頭 -> AprilTag 的座標
        t_cam_tag, R_cam_tag = self.get_transform('camera_link', 'tag36h11:0')

        if t_base_ee is not None and t_cam_tag is not None:
            self.R_gripper2base.append(R_base_ee)
            self.t_gripper2base.append(t_base_ee)
            self.R_target2cam.append(R_cam_tag)
            self.t_target2cam.append(t_cam_tag)
            print(f"✅ 成功記錄第 {len(self.t_gripper2base)} 組數據！")
        else:
            print("❌ 擷取失敗！請確保手臂靜止，且 RViz 中有看到 tag36h11:0 標籤。")

    def calculate(self):
        if len(self.t_gripper2base) < 3:
            print("⚠️ 至少需要 3 組數據才能計算！建議收集 5~10 組。")
            return

        print("🔄 開始計算手眼矩陣...")
        R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
            self.R_gripper2base, self.t_gripper2base,
            self.R_target2cam, self.t_target2cam,
            method=cv2.CALIB_HAND_EYE_TSAI
        )

        quat = R.from_matrix(R_cam2gripper).as_quat() # x, y, z, w
        
        print("\n" + "="*60)
        print("🎉 計算完成！請將下方這行指令複製起來：")
        print("這是專屬於你相機的靜態 TF 發布指令，可以直接貼到終端機執行：\n")
        print(f"ros2 run tf2_ros static_transform_publisher "
              f"{t_cam2gripper[0][0]:.5f} {t_cam2gripper[1][0]:.5f} {t_cam2gripper[2][0]:.5f} "
              f"{quat[0]:.5f} {quat[1]:.5f} {quat[2]:.5f} {quat[3]:.5f} "
              f"vx300s/ee_gripper_link camera_link")
        print("="*60 + "\n")

def main():
    rclpy.init()
    node = HandEyeCalibrator()
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    print("\n--- 📸 手眼校正程式已啟動 ---")
    while True:
        val = input("👉 按 [Enter] 紀錄當前姿態，輸入 [c] 計算結果，輸入 [q] 離開: ")
        if val.lower() == 'q': break
        elif val.lower() == 'c': node.calculate(); break
        else: node.sample()
    rclpy.shutdown()

if __name__ == '__main__':
    main()