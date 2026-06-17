# Project 1: 摘水果任務開發藍圖與待辦事項

## 階段一：相機基礎功能測試與 ROS 整合
- [ ] **前置作業與硬體連線測試**：
  1. 確認 RealSense 插在主機的 USB 3.0 藍色孔位。
  2. (**主機端**) 開放硬體權限與圖形介面：
     ```bash
     sudo chmod -R 777 /dev/bus/usb/
     sudo chmod 777 /dev/video*
     xhost +local:docker
     ```
  3. (**主機端**) 啟動並進入 Docker 環境：
     ```bash
     cd ~/jerry/viperx300s-VLA/docker
     ./run.sh
     ```
  4. (**Docker 內**) 確保成功印出相機資訊：
     ```bash
     rs-enumerate-devices
     ```

- [ ] **設定獨立通訊頻道 (ROS_DOMAIN_ID)**：
  避免與區網其他設備衝突，在終端機寫入專屬 ID (例如 42)。
  *(注意：因 Docker 特性，每次新開終端掛載進入容器後，請先手動執行以下指令，即刻生效)*
  ```bash
  docker exec -it viperx300s_robot bash
  export ROS_DOMAIN_ID=42
  echo $ROS_DOMAIN_ID
  ```

- [ ] **啟動 RealSense ROS2 節點**：(在終端機 1 執行)
  ```bash
  ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
  ```

- [ ] **驗證影像與深度 Topic**：(在終端機 2 執行)
  1. 確認 `$ROS_DOMAIN_ID` 與終端機 1 設定相同。
  2. 開啟視覺化工具：
     ```bash
     rviz2
     ```
  3. 新增 Image 顯示，並訂閱 `/camera/color/image_raw` 與 `/camera/aligned_depth_to_color/image_raw` 檢查畫面是否流暢。

---

## 階段二：手眼校正 (Hand-Eye Calibration) - Eye-in-Hand
- [ ] **硬體架設**：將相機穩固地鎖在手臂夾爪或末端關節上。注意：USB 線必須預留足夠的長度，避免手臂轉動時拉扯斷裂。
- [x] **準備校正圖卡**：已列印 AprilTag (Tag36h11 ID:0)，精準測量黑色正方形的邊長為 **16.0 cm (0.16 m)**，並平貼於桌面。
- [x] **啟動 AprilTag 辨識節點**：建立設定檔並啟動 `apriltag_ros` 節點，成功在 RViz2 看到圖卡 TF 座標。
- [x] **收集 TF 數據與計算**：已使用 `hand_eye_calibration.py` 收集 15 組數據並成功算出轉換矩陣。
- [x] **發布靜態 TF**：已將校正結果寫入 `launch/hand_eye.launch.py` 檔案中，可供永久使用。
  最終的發布指令 (ee_gripper_link -> camera_link) 為：
  ```bash
  ros2 run tf2_ros static_transform_publisher -0.12834 -0.95722 0.04688 -0.20474 0.03237 -0.04587 0.97720 vx300s/ee_gripper_link camera_link
  ```

---

## 階段三：視覺辨識模組開發 (摘水果)
- [ ] **整合 YOLO 模型**：撰寫 ROS2 Node，訂閱彩色影像 `/camera/color/image_raw`，用 YOLO 辨識出水果。
- [ ] **取得 2D 中心點與深度資訊**：計算出 Bounding Box 中心像素 `(u, v)`，並從對齊後的深度圖中取出距離 `z`。
- [ ] **相機內參轉換 (Deprojection)**：將 `(u, v, z)` 轉換成相機座標系下的 3D 座標 `(X, Y, Z)`。
- [ ] **TF 座標轉換**：利用 `tf2_ros`，將相機系 3D 座標轉換為手臂 `base_link` 座標系下的目標座標。

---

## 階段四：MoveIt2 控制與動作執行
- [ ] **撰寫 MoveIt2 控制腳本**：使用 MoveIt2 API。
- [ ] **設定夾取預備位置 (Pre-grasp Pose)**：手臂移動到目標上方約 5-10 公分處。
- [ ] **執行夾取動作**：
  1. 移動至預備位置。
  2. 垂直往下移動至目標座標。
  3. 閉合夾爪。
  4. 抬起並移動到水果籃位置。
  5. 張開夾爪。
- [ ] **異常處理與除錯**：捕捉錯誤避免手臂暴衝。

---

## 💡 附錄 A：日常開發啟動 SOP (手眼校正完成後)
每次重新開機，請開啟 **3 個終端機**（進入 Docker 後皆須先執行 `export ROS_DOMAIN_ID=42`）：
1. **終端機 1 (啟動手臂與 MoveIt2)**：
   `ros2 launch interbotix_xsarm_moveit xsarm_moveit.launch.py robot_model:=vx300s hardware_type:=actual`
2. **終端機 2 (啟動相機)**：
   `ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true`
3. **終端機 3 (發布手眼校正 TF)**：
   `ros2 launch /workspace/hand_eye.launch.py`
*(此時 RViz2 中應無黃色警告，且相機座標會跟著夾爪移動)*
4.開rviz2
rviz2

---

## 💡 附錄 B：重新校正 SOP (當相機被撞到或位置改變時)
1. 將 AprilTag 平貼桌面，確認硬體連線正常。
2. **終端機 1 & 2**：如附錄 A 啟動手臂與相機。
3. **終端機 3 (中止原本的 TF，改啟動 AprilTag 辨識)**：
   *(先按 Ctrl+C 關閉手眼 TF 發布，然後執行以下指令)*
   `ros2 run apriltag_ros apriltag_node --ros-args -r image_rect:=/camera/camera/color/image_raw -r camera_info:=/camera/camera/color/camera_info --params-file /workspace/tags.yaml`
4. **終端機 4 (執行校正程式)**：
   `python3 /workspace/hand_eye_calibration.py`
5. 透過 RViz2 (終端機 1) 移動手臂至 5~10 個不同角度，每次停穩後在終端機 4 按 `Enter` 記錄。
6. 收集完畢按 `c` 計算。
7. 將算出來的新指令中的數值 (x y z qx qy qz qw)，更新替換到 `/workspace/hand_eye.launch.py` 中即可。