# Project 1: 摘水果任務開發藍圖與待辦事項

## 階段一：相機基礎功能測試與 ROS 整合
- [ ] **前置作業與硬體連線測試**：
  1. 確認 RealSense 插在主機的 USB 3.0 藍色孔位。
  2. (主機端) 開放硬體權限：`sudo chmod -R 777 /dev/bus/usb/` 與 `sudo chmod 777 /dev/video*`。
  3. (主機端) 開放圖形介面權限：`xhost +local:docker`。
  4. (主機端) 執行 `./run.sh` 啟動並進入 Docker。
  5. 進入 Docker 內執行 `rs-enumerate-devices` 確保成功印出相機資訊。
- [ ] **設定獨立通訊頻道 (ROS_DOMAIN_ID)**：避免與區網其他設備衝突，在終端機寫入專屬 ID (例如 37)：
  `echo "export ROS_DOMAIN_ID=37" >> ~/.bashrc`
  `source ~/.bashrc`
- [ ] **啟動 RealSense ROS2 節點**：(在終端機 1 執行)
  `ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true`
- [ ] **驗證影像與深度 Topic**：(在終端機 2 執行)
  1. 確認 `echo $ROS_DOMAIN_ID` 與終端機 1 相同 (皆為 37)。
  2. 開啟視覺化工具：`rviz2`。
  3. 新增 Image 顯示，並訂閱 `/camera/color/image_raw` 與 `/camera/aligned_depth_to_color/image_raw` 檢查畫面是否流暢。

## 階段二：手眼校正 (Hand-Eye Calibration)
- [ ] **決定相機架設方式**：Eye-in-Hand (眼在手上) 或 Eye-to-Hand (眼在手外)。
- [ ] **利用 AprilTag 進行校正**：透過 ROS2 的 `tf2` 算出相機 (Camera_link) 與手臂基座 (vx300s/base_link) 的變換矩陣。
- [ ] **發布靜態 TF**：寫一支 `static_transform_publisher` 將相對關係發布到 ROS2 的 TF 樹上。

## 階段三：視覺辨識模組開發 (摘水果)
- [ ] **整合 YOLO 模型**：撰寫 ROS2 Node，訂閱彩色影像 `/camera/color/image_raw`，用 YOLO 辨識出水果。
- [ ] **取得 2D 中心點與深度資訊**：計算出 Bounding Box 中心像素 `(u, v)`，並從對齊後的深度圖中取出距離 `z`。
- [ ] **相機內參轉換 (Deprojection)**：將 `(u, v, z)` 轉換成相機座標系下的 3D 座標 `(X, Y, Z)`。
- [ ] **TF 座標轉換**：利用 `tf2_ros`，將相機系 3D 座標轉換為手臂 `base_link` 座標系下的目標座標。

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