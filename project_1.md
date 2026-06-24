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
- [x] **整合 YOLO 模型**：已撰寫 ROS2 Node `yolo_detector.py`，成功在 RViz2 顯示 YOLO 辨識框。
- [x] **取得 2D 中心點與深度資訊**：透過 `/camera/camera/aligned_depth_to_color/image_raw` 取得深度值。
- [x] **相機內參轉換 (Deprojection)**：利用相機內參矩陣將像素座標與深度轉換成 3D 空間座標。
- [x] **TF 座標轉換**：即時發布辨識目標的 TF 座標 (如 `target_banana`)。

---

## 階段四：MoveIt2 控制與動作執行
- [x] **撰寫 MoveIt2 控制腳本**：已撰寫 `pick_and_place.py`，整合 TF 監聽與 MoveIt2 API。
- [x] **設定夾取預備位置 (Pre-grasp Pose)**：腳本中已包含移動到目標上方 10cm 的邏輯。
- [x] **執行夾取動作**：腳本中已包含完整的「預備 -> 下降 -> 夾取 -> 抬起 -> 回 Home」流程，目前第六終端是單一路徑抓取，不是兩階段辨識確認。
- [ ] **硬體整合測試**：實際執行 `pick_and_place.py` 進行抓取測試。

---

## 階段五：進階兩階段抓取與自訂 AI 模型 (Two-Stage Grasping)
- [ ] **收集訓練資料**：利用相機拍攝真實水果與「蒂頭 (Stem)」的照片 (約 50-100 張)，涵蓋不同距離與角度。
- [ ] **標註與訓練 YOLO 模型**：使用標註工具 (如 Roboflow) 框出「水果」與「蒂頭」，並訓練/微調 YOLO 模型，匯出新的 `.pt` 權重檔。
- [ ] **開發兩階段抓取邏輯 (狀態機)**：改寫 `pick_and_place.py` 腳本：
  1. **粗略接近 (Coarse Approach)**：根據「水果」的 Bounding Box，將手臂移動到水果正上方約 15cm 處的「觀察點 (Hover Pose)」。
  2. **精確瞄準 (Fine Targeting)**：在觀察點讓相機重新對焦拍攝，取得清晰的「蒂頭」3D 座標。
  3. **夾取與扯斷 (Grasp & Pull)**：下降夾爪精準夾住蒂頭，並加入「向上抬起/微旋轉」的扯斷動作。

---

## 💡 附錄 A：最終抓取任務啟動 SOP (火力全開模式)
每次要執行完整的「視覺辨識與自動抓取」任務時，請依序執行以下步驟：

### 1. 前置作業 (主機端 Host)
```bash
sudo chmod 777 /dev/ttyUSB* /dev/video*
xhost +local:docker
cd ~/jerry/viperx300s-VLA/docker
./run.sh
```

### 2. 啟動各個 ROS 節點 (開啟 6 個終端機)
**每一個**終端機都要先執行這兩行指令進入環境：
```bash
docker exec -it viperx300s_robot bash
export ROS_DOMAIN_ID=42
```
然後，請依序在各個終端機輸入對應的啟動指令：

*   **終端機 1 (啟動相機)**：
    *(加入 `initial_reset:=true` 可在相機卡住時強制重置)*
    ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true initial_reset:=true

*   **終端機 2 (啟動手臂與 MoveIt2)**：
    ros2 launch interbotix_xsarm_moveit xsarm_moveit.launch.py robot_model:=vx300s hardware_type:=actual

*   **終端機 3 (發布手眼校正 TF)**：
    ros2 launch /workspace/hand_eye.launch.py

*   **終端機 4 (啟動 YOLO 辨識大腦)**：
    python3 /workspace/yolo_detector.py

*   **終端機 5 (開啟 RViz2 視覺化)**：
    rviz2

*   **終端機 6 (啟動總指揮 - 抓取程式)**：
    *(注意：此腳本需要 ROS 環境，需先 source)*
    source /opt/ros/humble/setup.bash
    source /workspace/ros2_ws/install/setup.bash
    python3 /workspace/pick_and_place.py [想抓的物體名稱]
    *(範例: `python3 /workspace/pick_and_place.py cup`，不加參數預設為 `bottle`)*
    *(流程說明：腳本會先等待 `target_<物體名稱>` 的 TF，接著再手動按 Enter 確認，之後執行預備位 -> 下降 -> 抓取 -> 抬起 -> 回 Home)*
    *(可攜性說明：repo 本身沒有綁死你的本機絕對路徑，但目標電腦仍需有相同的 ROS2 / MoveIt2 / 工作區安裝與相對路徑結構，否則需要先重新 build 或調整 source 路徑)*

---

## 💡 附錄 B：重新校正 SOP (當相機被撞到或位置改變時)
1. 將 AprilTag 平貼桌面，確認硬體連線正常。
2. **終端機 1 & 2**：如附錄 A 的步驟啟動手臂與相機。
3. **終端機 3 (中止原本的 TF，改啟動 AprilTag 辨識)**：
   *(先按 Ctrl+C 關閉手眼 TF 發布，然後執行以下指令)*
   `ros2 run apriltag_ros apriltag_node --ros-args -r image_rect:=/camera/camera/color/image_raw -r camera_info:=/camera/camera/color/camera_info --params-file /workspace/tags.yaml`
4. **終端機 4 (執行校正程式)**：
   `python3 /workspace/hand_eye_calibration.py`
5. 透過 RViz2 (終端機 2) 移動手臂至 5~10 個不同角度 (**務必包含扭動手腕的旋轉動作**)，每次停穩後在終端機 4 按 `Enter` 記錄。
6. 收集完畢按 `c` 計算。
7. 將算出來的新指令中的數值 (x y z qx qy qz qw)，更新替換到 `/workspace/hand_eye.launch.py` 中即可。

---

## 💡 附錄 C：如何永久安裝新的 Python 套件 (如 YOLO)
*(註：目前專案的 `Dockerfile` 已包含 `ultralytics` 和 `scipy`，此步驟僅供未來擴充參考)*
1. **編輯 Dockerfile**：打開專案中的 `docker/Dockerfile` 檔案。
2. **加入安裝指令**：在檔案末尾的 `RUN pip install ...` 區塊加入想安裝的套件名稱。
3. **重新建置 Image (在主機端)**：回到 `docker/` 資料夾，執行 `./build.sh`。
4. **完成**！未來執行 `./run.sh` 時，新開的容器就會內建這些套件。

---

## 💡 附錄 D：常見運行問題排除

### Q: YOLO 節點一直顯示「等待深度圖」，無法取得 3D 座標？
**A:** 這代表 `yolo_detector.py` 沒有收到深度影像。
1. **檢查 Topic 是否存在**：在任何一個終端機執行 `ros2 topic list | grep depth`。
2. **如果清單中「沒有」`/camera/camera/aligned_depth_to_color/image_raw`**：
   - 代表相機節點 (終端機 1) 啟動失敗。請回到該終端機，檢查是否有紅色錯誤訊息。
   - **最常見原因**：RealSense 相機沒有插在藍色的 **USB 3.0** 孔位，導致深度串流無法啟動。請關閉容器 (`docker compose down`)，換到正確的 USB 孔，再重新啟動所有流程。
   - **次要原因**：相機內部晶片當機，可嘗試使用 `initial_reset:=true` 參數強制重置 (已加入附錄 A)。
3. **如果清單中「有」該 Topic**：
   - 代表你的 YOLO 節點 (終端機 4) 或 RViz2 (終端機 5) 忘記設定 `export ROS_DOMAIN_ID=42`，導致收不到資訊。請在對應的終端機重新設定。
   - **QoS 不匹配**：`yolo_detector.py` 訂閱時需使用 `qos_profile_sensor_data` 才能接收 RealSense 的影像串流 (已在程式碼中修正)。

---

## 💡 附錄 E：實用偵錯指令
*   **查詢手臂夾爪當前相對於底座的 3D 座標**：
    `ros2 run tf2_ros tf2_echo vx300s/base_link vx300s/ee_gripper_link`
*   **查詢手臂各關節馬達的當前角度 (單位: 弧度)**：
    `ros2 topic echo /vx300s/joint_states`

---

## 💡 附錄 F：關閉 Docker 環境的差別(cd docker)
### `docker compose down` (推薦使用 🌟)
*   **作用**：將容器**「停止，並且完全刪除」**。
*   **優點**：可以確保 Docker 完全釋放對 USB 硬體 (手臂 `/dev/ttyUSB0`、相機 `/dev/video*`) 的佔用。下次執行 `./run.sh` 時，會得到一個乾淨、重新綁定好硬體的新環境，最不容易遇到「找不到設備」的 Bug。
*   **檔案安全**：不用擔心檔案不見。因為你的 `/workspace` 資料夾有設定「掛載 (Volume)」，所以就算容器被刪除了，你的程式碼、設定檔都還是會保留在你的電腦主機上。
### `./stop.sh` (或 `docker compose stop`)
*   **作用**：只是讓容器**「暫停 / 睡著」**，容器的本體還留在系統裡。
*   **缺點**：因為容器還活著，有時候會緊緊咬住主機的 USB 設備不放。如果你拔插了相機或手臂，再把它喚醒時，很容易發生「Device is busy」或抓不到硬體的錯誤。
*   **結論**：為了硬體連線的穩定性，**強烈建議你以後都直接用 `docker compose down` 來關閉環境！**
